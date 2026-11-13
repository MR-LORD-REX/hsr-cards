"""Version-aware data loading shared by the Nanoka character cards.

The card renderers were originally standalone scripts with their own data
loading. This module gives the SDK one place that resolves a character by
id or name, loads a pinned version (or two versions for a comparison card),
and downloads only the assets the cards actually draw.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from ...nanoka import Locale, NanokaClient
from ...nanoka.exceptions import NanokaCacheError, NanokaNotFoundError
from ...nanoka.models import CharacterDetail, CharacterSummary

DEFAULT_LOCALE = "en"
RANK_ASSET_DIR = "rank/_dependencies/textures"


@dataclass
class CharacterData:
    """One character at one Nanoka version, with resolved display data."""

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
        record_name = self.catalog_record.get(self.locale) or self.catalog_record.get("en")
        return str(record_name or self.detail.name or self.character_id)

    @property
    def description(self) -> str:
        desc = self.detail.desc or self.catalog_record.get("desc") or ""
        return clean_text(desc)

    @property
    def element(self) -> str:
        return (self.detail.element or "").lower()

    @property
    def path(self) -> str:
        return (self.detail.path_codename or "").lower()

    @property
    def stars(self) -> int:
        return self.summary.stars or self.detail.stars or 5

    async def asset(self, relative: str) -> Path | None:
        """Download one asset into this version's cache and return its path."""
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
    """Resolve ``None`` to the newest published Nanoka build."""
    if version:
        return str(version)
    client = NanokaClient(cache_dir=cache_dir, include_assets=False)
    try:
        await client.initialize()
        return client.version
    finally:
        await client.close()


def normalize_locale(locale: Locale | str | None) -> str:
    return Locale.normalize(locale or DEFAULT_LOCALE).value


def parse_versions(
    version: str | Sequence[str] | None,
) -> tuple[str | None, str | None]:
    """Return ``(from_version, to_version)`` for single or comparison cards.

    A string is a single version; a two-item sequence is a comparison with the
    older version first. More than two versions is rejected because the cards
    have no room for a third column of changes.
    """
    if version is None:
        return None, None
    if isinstance(version, str):
        return version, None
    values = [str(item) for item in version if item]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], None
    if len(values) > 2:
        raise ValueError("At most two versions can be compared (from, to).")
    return values[0], values[1]


def version_label(
    version: str | None,
    compare_from: str | None = None,
    compare_to: str | None = None,
) -> str:
    if compare_from and compare_to:
        return f"{compare_from} \u2192 {compare_to}"
    return version or compare_to or ""


_HASH_WIDTH = 10


def safe_filename(value: str, *, limit: int = 72) -> str:
    """Return a stable, readable filenames component for card caches."""
    cleaned = re.sub(r"[^\w.-]+", "_", str(value).strip(), flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    if not cleaned:
        cleaned = "unknown"
    if len(cleaned) <= limit:
        return cleaned
    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:_HASH_WIDTH]
    return f"{cleaned[: limit - _HASH_WIDTH - 1].rstrip('._-')}_{digest}"


def comparison_key(versions: Sequence[str]) -> str:
    return "--".join(safe_filename(version, limit=24) for version in versions)


def default_rendered_cache_dir() -> Path:
    return Path.cwd() / ".hsr_cards_rendered"


class RenderedCardCache:
    """Cache rendered Nanoka cards that do not depend on a player UID.

    Files are named ``{character}_{card_type}_{version}.png``. A comparison
    card uses both builds joined with ``--`` so either render order remains
    discoverable: ``1511_skills_4.6.51--4.6.54.png``.
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        enabled: bool = True,
    ):
        self.root = Path(root or default_rendered_cache_dir()).expanduser().resolve()
        self.enabled = enabled

    def path(
        self,
        character: str | int,
        card_type: str,
        version: str | Sequence[str],
        *,
        locale: str = "en",
    ) -> Path:
        versions = [version] if isinstance(version, str) else list(version)
        key = comparison_key(versions)
        suffix = "" if normalize_locale(locale) == DEFAULT_LOCALE else f"_{normalize_locale(locale)}"
        return self.root / (
            f"{safe_filename(character)}_{safe_filename(card_type)}_"
            f"{key}{suffix}.png"
        )

    def load(
        self,
        character: str | int,
        card_type: str,
        version: str | Sequence[str],
        *,
        locale: str = "en",
    ) -> Image.Image | None:
        if not self.enabled:
            return None
        path = self.path(character, card_type, version, locale=locale)
        if not path.is_file():
            return None
        try:
            image = Image.open(path)
            image.load()
            return image.convert("RGBA")
        except (OSError, ValueError):
            return None

    def save(
        self,
        image: Image.Image,
        character: str | int,
        card_type: str,
        version: str | Sequence[str],
        *,
        locale: str = "en",
    ) -> Path:
        path = self.path(character, card_type, version, locale=locale)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGBA").save(path, format="PNG", optimize=True)
        return path

    def clear(self, version: str | None = None) -> int:
        """Delete matching rendered cards; returns the number removed."""
        if not self.root.is_dir():
            return 0
        removed = 0
        token = f"_{safe_filename(version, limit=24)}" if version else None
        for path in self.root.glob("*.png"):
            if token and token not in path.stem:
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed
async def load_character(
    identifier: int | str,
    *,
    version: str | None = None,
    locale: Locale | str = DEFAULT_LOCALE,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> CharacterData:
    """Load a character by id or name at one pinned Nanoka version."""
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
    except BaseException:
        await client.close()
        raise
    catalog = await _catalog(client, "character.json")
    items = await _catalog(client, "item.json")
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
    """Load the same character at two versions for a comparison card."""
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
        await before.close()
        raise
    return before, after


async def close_all(*characters: CharacterData) -> None:
    for character in characters:
        await character.client.close()


def skill_icon_relative(character_id: int, suffix: str) -> str:
    return f"skillicons/SkillIcon_{character_id}_{suffix}.webp"


def rank_texture_relative(character_id: int, rank: int | str) -> str:
    return f"{RANK_ASSET_DIR}/{character_id}/{character_id}_Rank_{rank}.webp"


def rank_icon_relative(rank_icon: str | None) -> str | None:
    """Map a Nanoka ``SkillIcon_1415_Rank1.png`` icon path to its webp."""
    if not rank_icon:
        return None
    stem = Path(str(rank_icon).replace("\\", "/")).stem
    return f"skillicons/{stem}.webp" if stem else None


def drawcard_relative(character_id: int | str) -> str:
    return f"avatardrawcard/{character_id}.webp"


def element_relative(element: str | None) -> str | None:
    return f"element/{element}.webp" if element else None


def path_relative(path: str | None) -> str | None:
    return f"pathicon/{path}.webp" if path else None


def item_relative(item_id: int | str) -> str:
    return f"itemfigures/{item_id}.webp"


def version_datetime(version: str) -> datetime | None:
    """Parse a Nanoka build label; used only for deterministic ordering."""
    try:
        parts = [int(part) for part in version.split(".") if part.isdigit()]
    except ValueError:
        return None
    if not parts:
        return None
    return datetime(parts[0], parts[1] if len(parts) > 1 else 1, 1)


async def prime_assets(character: CharacterData, relatives: Sequence[str]) -> dict[str, Path]:
    """Fetch a set of assets for one version, skipping unresolved entries."""
    result: dict[str, Path] = {}
    for relative in dict.fromkeys(item for item in relatives if item):
        path = await character.asset(relative)
        if path is not None:
            result[relative] = path
    return result


__all__ = [
    "CharacterData",
    "clean_text",
    "close_all",
    "drawcard_relative",
    "element_relative",
    "item_relative",
    "load_character",
    "load_pair",
    "normalize_locale",
    "parse_versions",
    "path_relative",
    "prime_assets",
    "rank_icon_relative",
    "rank_texture_relative",
    "resolve_version",
    "skill_icon_relative",
    "version_label",
]
