"""Resolve character versions, catalog entries, and provider ownership for cards."""
from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from PIL import Image
from ..clients.nanoka import NanokaClient
from ..providers.nanoka.locales import Locale
from ..providers.nanoka.exceptions import NanokaCacheError, NanokaNotFoundError
from ..providers.nanoka.models import CharacterDetail, CharacterSummary
from ..core.locale import DEFAULT_LOCALE, normalize_locale
from ..core.paths import comparison_key, default_rendered_cache_dir, safe_filename
from ..core.versions import parse_versions, version_datetime, version_label
from .rendered_cache import RenderedCardCache
from .character_assets import (
    RANK_ASSET_DIR, drawcard_relative, element_relative, item_relative, path_relative,
    prime_assets, rank_icon_relative, rank_texture_relative, skill_icon_relative,
)

__all__ = [
    "CharacterData", "clean_text", "close_all", "drawcard_relative",
    "element_relative", "item_relative", "load_character", "load_pair",
    "normalize_locale", "parse_versions", "path_relative", "prime_assets",
    "rank_icon_relative", "rank_texture_relative", "resolve_version",
    "skill_icon_relative", "version_label",
]


@dataclass
class CharacterData:
    """One character's catalog/detail data at a resolved Nanoka build and locale.

    client supplies targeted asset requests and stays owned by the caller of the
    loader. Call client.close() or close_all() after preparing/rendering this data.
    """

    character_id: int
    version: str
    locale: str
    summary: CharacterSummary
    detail: CharacterDetail
    catalog_record: dict[str, Any]
    items: dict[str, Any]
    client: NanokaClient
    detail_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Return the locale catalog name, then English/detail name, then the character ID."""
        record_name = self.catalog_record.get(self.locale) or self.catalog_record.get("en")
        return str(record_name or self.detail.name or self.character_id)

    @property
    def description(self) -> str:
        """Return the cleaned detail description, falling back to the catalog description."""
        desc = self.detail.desc or self.catalog_record.get("desc") or ""
        return clean_text(desc)

    @property
    def element(self) -> str:
        """Return the lowercase element codename, or an empty string when unknown."""
        return (self.detail.element or "").lower()

    @property
    def path(self) -> str:
        """Return the lowercase path codename, or an empty string when unknown."""
        return (self.detail.path_codename or "").lower()

    @property
    def stars(self) -> int:
        """Return summary/detail rarity, falling back to five stars when absent."""
        return self.summary.stars or self.detail.stars or 5

    async def asset(self, relative: str) -> Path | None:
        """Fetch one CDN-relative asset into this character's version/locale cache.

        Return its local Path, or None for an empty/unresolved asset. Downloads and cache
        writes use the existing caller-owned client; provider errors propagate.
        """
        if not relative:
            return None
        return await self.client.fetch_asset(relative)


def clean_text(value: str | None) -> str:
    """Strip Nanoka markup and collapse escaped paragraph breaks."""
    if not value:
        return ""
    import re

    text = value.replace("\\n", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


async def resolve_version(
    version: str | None, *, cache_dir: str | Path | None = None
) -> str:
    """Return an explicit build unchanged, or resolve None to Nanoka's newest build.

    cache_dir overrides the caller-relative provider cache. The unpinned case may
    request/cache metadata and catalogs; its temporary client is always closed.
    Provider/cache failures propagate.
    """
    if version:
        return str(version)
    client = NanokaClient(cache_dir=cache_dir, include_assets=False)
    try:
        await client.initialize()
        return client.version
    finally:
        await client.close()


async def load_character(
    identifier: int | str,
    *,
    version: str | None = None,
    locale: Locale | str = DEFAULT_LOCALE,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> CharacterData:
    """Resolve a Nanoka ID or published name into one CharacterData object.

    version=None selects the newest published build; an explicit string pins it.
    locale accepts Nanoka aliases and defaults to en. cache_dir overrides provider
    storage and proxy configures requests. Catalog/detail loading may write cache
    files; bulk artwork is deferred to targeted asset calls.

    Unknown characters raise NanokaNotFoundError; locale/model/provider errors
    propagate. On success the returned data owns an open-capable client that the
    caller must close. Failures, including cancellation, close that client first.
    """
    loc = normalize_locale(locale)
    client = NanokaClient(
        version=version,
        language=loc,
        cache_dir=cache_dir,
        proxy=proxy,
        include_assets=False,
    )
    try:
        await client.initialize()
        summary, detail = await _resolve_character(client, identifier)
        catalog = await _catalog(client, "character.json")
        items = await _catalog(client, "item.json")
    except BaseException:
        await client.close()
        raise
    record = catalog.get(str(summary.id)) or {}
    data = CharacterData(
        character_id=summary.id,
        version=client.version,
        locale=loc,
        summary=summary,
        detail=detail,
        catalog_record=record,
        items=items,
        detail_payload=detail.model_dump(mode="json"),
        client=client,
    )
    return data


async def _resolve_character(
    client: NanokaClient, identifier: int | str
) -> tuple[CharacterSummary, CharacterDetail]:
    value = str(identifier).strip()
    if value.isdigit():
        summaries = await client.list_characters()
        summary = next((item for item in summaries if str(item.id) == value), None)
        if summary is None:
            try:
                detail = await client.get_character_detail(int(value))
            except NanokaNotFoundError as exc:
                raise NanokaNotFoundError("character", identifier) from exc
            summary = CharacterSummary.from_entry(
                int(value), {"en": detail.name, "damageType": detail.damage_type,
                             "baseType": detail.base_type, "rank": detail.rarity}
            )
        else:
            detail = await client.get_character_detail(summary.id)
        return summary, detail
    character = await client.get_character(name=value)
    if character is None or character.detail is None:
        raise NanokaNotFoundError("character", identifier)
    return character.summary, character.detail


async def _catalog(client: NanokaClient, name: str) -> dict[str, Any]:
    try:
        payload = await client.cache.load_json(name)
    except NanokaCacheError:
        return {}
    return payload if isinstance(payload, dict) else {}


async def load_pair(
    identifier: int | str,
    from_version: str,
    to_version: str,
    *,
    locale: Locale | str = DEFAULT_LOCALE,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[CharacterData, CharacterData]:
    """Load the same ID/name at ordered from_version and to_version builds.

    locale/cache_dir/proxy follow load_character(). Return (before, after) with
    independent versioned data clients; the caller must close both. Loading failures
    propagate, closing the first client if loading the second fails.
    """
    before = await load_character(
        identifier,
        version=from_version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
    )
    try:
        after = await load_character(
            identifier,
            version=to_version,
            locale=locale,
            cache_dir=cache_dir,
            proxy=proxy,
        )
    except BaseException:
        await before.client.close()
        raise
    return before, after


async def close_all(*characters: CharacterData) -> None:
    """Close the clients attached to each supplied CharacterData in argument order.

    Await on the clients' event loop. Clients are treated as caller-owned resources
    explicitly released here; a close failure propagates and stops later closes.
    """
    for character in characters:
        await character.client.close()
