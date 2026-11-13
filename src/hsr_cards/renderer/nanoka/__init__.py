"""Nanoka character cards.

Public entry points mirror the Nanoka SDK's identifier rules:

* no version: newest published build
* one version: a card for that build
* two versions: an inline comparison of the newer build against the older one
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from PIL import Image

from .character_skills import build_comparison_data as build_comparison_skills
from .character_skills import build_skill_data, load_character as skills_load_character
from .character_skills import render_full
from .character_variants import build_card_data, build_comparison_card_data, render_detail
from .data import CharacterData, close_all, load_character, normalize_locale, parse_versions
from .data import RenderedCardCache, default_rendered_cache_dir

__all__ = [
    "BatchCardResult",
    "BatchRenderResult",
    "CharacterData",
    "build_card_data",
    "build_comparison_card_data",
    "build_comparison_skills",
    "build_skill_data",
    "close_all",
    "get_character_info",
    "get_character_skills",
    "load_character",
    "normalize_locale",
    "parse_versions",
    "render_all_info",
    "render_all_skills",
    "render_detail",
    "render_full",
]


class InfoCardResult:
    """Rendered info card with optional cached-card metadata."""

    def __init__(self, image: Image.Image, *, character: str, version: str | Sequence[str], cache_path: Path | None = None):
        self.image = image
        self.character = character
        self.version = version
        self.cache_path = cache_path

    def save(self, *args, **kwargs):
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.image, name)


async def get_character_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> InfoCardResult:
    """Render the character detail card.

    ``version`` accepts a single build string or a two-item sequence
    ``(from_version, to_version)`` for an inline version comparison. Omitting
    it uses the newest published Nanoka build.
    """
    from_version, to_version = parse_versions(version)
    if to_version:
        data, before, after = await build_comparison_card_data(
            identifier, from_version, to_version, locale=locale, cache_dir=cache_dir, proxy=proxy
        )
        try:
            versions = (data.before.version, data.version)
            cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
            cached = None if force_refresh else cache.load(data.name, "info", versions, locale=locale)
            if cached is not None:
                return InfoCardResult(cached, character=data.name, version=versions)
            image = render_detail(data)
            path = cache.save(image, data.name, "info", versions, locale=locale) if use_rendered_cache else None
            return InfoCardResult(image, character=data.name, version=versions, cache_path=path)
        finally:
            await close_all(before, after)
    character = await load_character(
        identifier, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy
    )
    try:
        data = await build_card_data(character)
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        cached = None if force_refresh else cache.load(data.name, "info", data.version, locale=locale)
        if cached is not None:
            return InfoCardResult(cached, character=data.name, version=data.version)
        image = render_detail(data)
        path = cache.save(image, data.name, "info", data.version, locale=locale) if use_rendered_cache else None
        return InfoCardResult(image, character=data.name, version=data.version, cache_path=path)
    finally:
        await character.client.close()


async def get_character_skills(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
):
    """Render the full character skills sheet and its rich-message payloads.

    ``version`` follows the same single/comparison rules as
    :func:`get_character_info`.
    """
    from_version, to_version = parse_versions(version)
    if to_version:
        data, before, after = await build_comparison_skills(
            identifier, from_version, to_version, locale=locale, cache_dir=cache_dir, proxy=proxy
        )
        try:
            versions = (data.version_before, data.version_after)
            result = render_full(data)
            cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
            cached = None if force_refresh else cache.load(data.name, "skills", versions, locale=locale)
            if cached is not None:
                result.image = cached
            elif use_rendered_cache:
                cache.save(result.image, data.name, "skills", versions, locale=locale)
            return result
        finally:
            await close_all(before, after)
    character = await skills_load_character(
        identifier, locale=locale, version=from_version, cache_dir=cache_dir, proxy=proxy
    )
    try:
        data = await build_skill_data(character)
        result = render_full(data)
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        cached = None if force_refresh else cache.load(data.name, "skills", data.version, locale=locale)
        if cached is not None:
            result.image = cached
        elif use_rendered_cache:
            cache.save(result.image, data.name, "skills", data.version, locale=locale)
        return result
    finally:
        await character.client.close()


@dataclass
class BatchCardResult:
    """One character's outcome from a batch render."""

    identifier: int | str
    result: InfoCardResult | "SkillsCardResult" | None = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def image(self) -> Image.Image | None:
        return self.result.image if self.result is not None else None


@dataclass
class BatchRenderResult:
    """Batch render summary; one failure never aborts the other characters."""

    items: list[BatchCardResult] = field(default_factory=list)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def succeeded(self) -> list[BatchCardResult]:
        return [item for item in self.items if item.ok]

    @property
    def failed(self) -> list[BatchCardResult]:
        return [item for item in self.items if not item.ok]

    @property
    def errors(self) -> dict[int | str, Exception]:
        return {item.identifier: item.error for item in self.items if item.error is not None}

    @property
    def images(self) -> list[Image.Image]:
        return [item.result.image for item in self.succeeded if item.result is not None]


async def _batch_identifiers(
    identifiers: Sequence[int | str] | None,
    *,
    version: str | None,
    include_beta: bool,
    cache_dir: str | Path | None,
) -> list[int | str]:
    if identifiers is not None:
        return list(dict.fromkeys(identifiers))
    from ...nanoka import NanokaClient

    client = NanokaClient(version=version, cache_dir=cache_dir, include_assets=False)
    try:
        await client.initialize()
        summaries = await client.list_characters(include_beta=include_beta)
    finally:
        await client.close()
    return [summary.id for summary in summaries]


async def _run_batch(
    renderer_name: str,
    identifiers: Sequence[int | str] | None,
    version: str | Sequence[str] | None,
    *,
    locale: str,
    cache_dir: str | Path | None,
    proxy: str | None,
    rendered_cache_dir: str | Path | None,
    use_rendered_cache: bool,
    concurrency: int,
    include_beta: bool,
) -> BatchRenderResult:
    # validate the shape once, before spending time listing characters
    from_version, _to_version = parse_versions(version)
    targets = await _batch_identifiers(identifiers, version=from_version, include_beta=include_beta, cache_dir=cache_dir)
    renderer = globals()[renderer_name]
    limit = asyncio.Semaphore(max(1, int(concurrency)))
    items: list[BatchCardResult] = []

    async def render_one(identifier: int | str) -> BatchCardResult:
        async with limit:
            try:
                result = await renderer(
                    identifier,
                    version,
                    locale=locale,
                    cache_dir=cache_dir,
                    proxy=proxy,
                    rendered_cache_dir=rendered_cache_dir,
                    use_rendered_cache=use_rendered_cache,
                    force_refresh=True,
                )
            except Exception as exc:
                return BatchCardResult(identifier=identifier, error=exc)
            return BatchCardResult(identifier=identifier, result=result)

    outcomes = await asyncio.gather(
        *(render_one(identifier) for identifier in targets), return_exceptions=True
    )
    for identifier, outcome in zip(targets, outcomes):
        if isinstance(outcome, BaseException):
            items.append(BatchCardResult(identifier=identifier, error=outcome))
        else:
            items.append(outcome)
    return BatchRenderResult(items)


async def render_all_info(
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    concurrency: int = 4,
    include_beta: bool = True,
    identifiers: Sequence[int | str] | None = None,
) -> BatchRenderResult:
    """Render info cards for every Nanoka character concurrently.

    Cards are always rerendered, even when a matching file already exists in
    ``.hsr_cards_rendered/``; the fresh image replaces the cached one. One
    character failing is reported in :class:`BatchRenderResult` and does not
    cancel the rest. ``version`` follows the single/comparison rules used by
    :func:`get_character_info`.
    """
    return await _run_batch(
        "get_character_info",
        identifiers,
        version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
        rendered_cache_dir=rendered_cache_dir,
        use_rendered_cache=use_rendered_cache,
        concurrency=concurrency,
        include_beta=include_beta,
    )


async def render_all_skills(
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    concurrency: int = 4,
    include_beta: bool = True,
    identifiers: Sequence[int | str] | None = None,
) -> BatchRenderResult:
    """Render skills/eidolon sheets for every Nanoka character concurrently.

    Uses the same rerender-and-continue semantics as :func:`render_all_info`.
    """
    return await _run_batch(
        "get_character_skills",
        identifiers,
        version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
        rendered_cache_dir=rendered_cache_dir,
        use_rendered_cache=use_rendered_cache,
        concurrency=concurrency,
        include_beta=include_beta,
    )
