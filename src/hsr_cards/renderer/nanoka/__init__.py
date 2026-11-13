"""Nanoka character cards.

Public entry points mirror the Nanoka SDK's identifier rules:

* no version: newest published build
* one version: a card for that build
* two versions: an inline comparison of the newer build against the older one
"""

from __future__ import annotations

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
            cached = cache.load(data.name, "info", versions, locale=locale)
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
        cached = cache.load(data.name, "info", data.version, locale=locale)
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
            cached = cache.load(data.name, "skills", versions, locale=locale)
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
        cached = cache.load(data.name, "skills", data.version, locale=locale)
        if cached is not None:
            result.image = cached
        elif use_rendered_cache:
            cache.save(result.image, data.name, "skills", data.version, locale=locale)
        return result
    finally:
        await character.client.close()
