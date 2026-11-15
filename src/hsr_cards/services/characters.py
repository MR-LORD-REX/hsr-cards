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

from ..renderer.nanoka.character_skills import build_comparison_data as build_comparison_skills
from ..renderer.nanoka.character_skills import build_skill_data, load_character as skills_load_character
from ..renderer.nanoka.character_skills import render_full
from ..renderer.nanoka.character_variants import build_card_data, build_comparison_card_data, render_detail
from ..renderer.nanoka.data import CharacterData, close_all, load_character, normalize_locale, parse_versions
from ..renderer.nanoka.data import RenderedCardCache, default_rendered_cache_dir
from ..renderer.nanoka.light_cone import LCInfoCardResult, get_LC_info
from ..renderer.nanoka.relic import RelicInfoCardResult, get_relic_info
from ..renderer.nanoka.item import ItemInfoCardResult, get_item_info


__all__ = [
    "InfoCardResult",
    "BatchCardResult",
    "BatchRenderResult",
    "CharacterData",
    "build_card_data",
    "build_comparison_card_data",
    "build_comparison_skills",
    "build_skill_data",
    "close_all",
    "get_character_info",
    "get_LC_info",
    "LCInfoCardResult",
    "get_relic_info",
    "RelicInfoCardResult",
    "get_item_info",
    "ItemInfoCardResult",
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
        """Wrap image plus character/version metadata without copying the PIL image.

        version is one build or an ordered comparison pair. cache_path is optional;
        constructing the result does not save a file or open a provider resource.
        """
        self.image = image
        self.character = character
        self.version = version
        self.cache_path = cache_path

    def save(self, *args, **kwargs):
        """Save the wrapped image with PIL.Image.save arguments.

        The destination, format and encoder options are passed through unchanged;
        filesystem and encoder exceptions propagate.
        """
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name: str):
        """Forward unresolved attributes, such as size, to the wrapped PIL image."""
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
    """Render one character detail card or an inline version comparison.

    identifier accepts a numeric Nanoka ID or published character name. version=None
    selects the newest published build; a string pins one build, and a two-item
    sequence supplies (older, newer). More than two versions raises ValueError.
    locale defaults to en and accepts Nanoka locale aliases. cache_dir selects the
    downloaded-data root, proxy configures provider requests, and rendered_cache_dir
    selects the generated-image root (default .hsr_cards_rendered in the caller's cwd).

    Return InfoCardResult with image, resolved character name/version and an optional
    path for newly saved images. use_rendered_cache=False disables image-cache IO;
    force_refresh bypasses image-cache reads. Loading may still request/cache provider
    data. Unknown characters, invalid data and provider/render/file errors propagate.
    All Nanoka clients created by this operation are closed, including on failure.
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
    """Render the full skills/eidolon sheet and its rich-message payloads.

    identifier accepts a Nanoka ID or published name. version=None selects the newest
    build, a string pins one build, and (older, newer) compares two builds inline.
    Invalid version-sequence lengths raise ValueError. locale defaults to en;
    cache_dir/proxy configure provider data, while rendered_cache_dir defaults to
    .hsr_cards_rendered in the caller's cwd.

    Return SkillsCardResult containing image, tables, label-to-table dropdown indices,
    labeled table_models and skills/eidolons/materials sections. Payloads are rebuilt
    even when the image is cached. force_refresh bypasses image-cache reads;
    use_rendered_cache=False disables image-cache IO. Provider/model/render errors
    propagate, and operation-created clients are always closed.
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
        """Return True when this item has no stored exception, even if its result is absent."""
        return self.error is None

    @property
    def image(self) -> Image.Image | None:
        """Return the rendered PIL image, or None when no result was produced."""
        return self.result.image if self.result is not None else None


@dataclass
class BatchRenderResult:
    """Batch render summary; one failure never aborts the other characters."""

    items: list[BatchCardResult] = field(default_factory=list)

    def __iter__(self):
        """Iterate per-character outcomes in the batch input order."""
        return iter(self.items)

    def __len__(self) -> int:
        """Return the total number of recorded character outcomes."""
        return len(self.items)

    @property
    def succeeded(self) -> list[BatchCardResult]:
        """Return outcomes with no stored exception, preserving input order."""
        return [item for item in self.items if item.ok]

    @property
    def failed(self) -> list[BatchCardResult]:
        """Return outcomes with a stored exception, preserving input order."""
        return [item for item in self.items if not item.ok]

    @property
    def errors(self) -> dict[int | str, Exception]:
        """Return identifier-to-exception entries for failed characters."""
        return {item.identifier: item.error for item in self.items if item.error is not None}

    @property
    def images(self) -> list[Image.Image]:
        """Return successful PIL images, omitting absent results and preserving input order."""
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
    from ..clients.nanoka import NanokaClient

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
    from importlib import import_module

    renderer = getattr(import_module("hsr_cards.renderer.nanoka"), renderer_name)
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

    outcomes = await asyncio.gather(*(render_one(identifier) for identifier in targets))
    items.extend(outcomes)
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
    """Rerender character info cards concurrently and collect every outcome.

    version accepts newest (None), pinned (string), or (older, newer) comparison builds.
    identifiers optionally limits the batch to IDs/names, removing duplicates while
    preserving order. Otherwise the catalog is listed with include_beta=True by
    default. concurrency defaults to four and is clamped to at least one worker.
    locale defaults to en; cache_dir/proxy configure Nanoka data and requests;
    rendered_cache_dir selects generated images in the caller-relative cache root.

    Return BatchRenderResult in input order. Each card forces a fresh image and
    replaces its cache file unless use_rendered_cache=False. Per-character Exceptions
    are stored rather than aborting siblings; cancellation propagates. Catalog/version
    failures propagate before rendering. Listing and render clients are operation-owned
    and closed by their respective services.
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
    """Rerender character skills/eidolon sheets concurrently and collect outcomes.

    version accepts newest (None), pinned (string), or ordered comparison builds.
    identifiers limits the catalog to IDs/names; otherwise include_beta controls
    unreleased entries. concurrency defaults to four, with a minimum of one worker.
    locale/cache_dir/proxy/rendered_cache_dir have the same meanings as
    get_character_skills(); use_rendered_cache=False disables generated-image IO.

    Return BatchRenderResult in input order. Cached images are always replaced by
    fresh renders. Per-character Exceptions are stored; cancellation and catalog
    failures propagate. Every service closes the provider clients it creates.
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
