"""Pure catalog filtering, ordering, and asset alias resolution."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, TypeVar


from .locales import DEFAULT_LOCALE, Locale
from .models import CharacterSummary, ItemSummary, LightConeSummary, MonsterSummary, RelicSetSummary

T = TypeVar("T")


def matches_text(item: Any, search: str | None, language: Locale) -> bool:
    """Match search case-insensitively against localized names and common name fields.

    An empty search matches all entries. The requested language is checked before
    English, Chinese, Japanese, and Korean; this pure helper performs no IO.
    """
    if not search:
        return True
    needle = search.casefold()
    for lang in (language.value, "en", "zh", "ja", "ko"):
        value = getattr(item, lang, None)
        if value and needle in str(value).casefold():
            return True
    for key in ("name", "item_name", "title"):
        value = getattr(item, key, None)
        if value and needle in str(value).casefold():
            return True
    return False

def normalize_filter(value: str | None) -> str | None:
    """Casefold a filter and remove hyphens/underscores, or return None if empty."""
    return value.strip().casefold().replace("-", "").replace("_", "") if value else None

def apply_extra_filters(items: Iterable[T], filters: dict[str, Any]) -> list[T]:
    """Return entries whose attributes equal each non-None filter value.

    Unknown attributes behave as None. The input is copied and no IO is performed.
    """
    if not filters:
        return list(items)
    result = list(items)
    for key, expected in filters.items():
        if expected is None:
            continue
        result = [item for item in result if getattr(item, key, None) == expected]
    return result

def _filter_characters(
    items: Iterable[CharacterSummary],
    *,
    element: str | None,
    path: str | None,
    rarity: int | None,
    released: bool | None,
    include_beta: bool,
    search: str | None,
    extra: dict[str, Any],
) -> list[CharacterSummary]:
    result = list(items)
    if not include_beta:
        result = [item for item in result if item.release is not None]
    if released is not None:
        result = [item for item in result if (item.release is not None) == released]
    if element:
        needle = normalize_filter(element)
        result = [item for item in result if normalize_filter(item.damage_type) == needle]
    if path:
        needle = normalize_filter(path)
        result = [
            item
            for item in result
            if normalize_filter(item.base_type) == needle
            or normalize_filter(item.path) == needle
        ]
    if rarity is not None:
        result = [item for item in result if item.stars == rarity]
    if search:
        result = [item for item in result if matches_text(item, search, DEFAULT_LOCALE)]
    return apply_extra_filters(result, extra)

def sort_characters(
    items: Iterable[CharacterSummary],
    *,
    sort_by: str,
    ascending: bool,
    locale: Locale | str,
) -> list[CharacterSummary]:
    """Copy/order characters by release, ID, rarity, or localized name.

    Unknown sort_by values use release; ascending=False reverses the ordering.
    Invalid locale aliases raise ValueError and missing sort values use zero/empty text.
    """
    loc = Locale.normalize(locale)
    keys = {
        "release": lambda item: (item.release is not None, item.release or 0, item.id),
        "id": lambda item: item.id,
        "rarity": lambda item: (item.stars or 0, item.id),
        "name": lambda item: (item.display_name(loc) or "").casefold(),
    }
    return sorted(items, key=keys.get(sort_by, keys["release"]), reverse=not ascending)

def filter_lightcones(
    items: Iterable[LightConeSummary],
    *,
    path: str | None,
    rarity: int | None,
    search: str | None,
    language: Locale | str,
) -> list[LightConeSummary]:
    """Copy/filter light cones by normalized path, rarity, and localized search.

    None filters are ignored; invalid language aliases raise ValueError. No IO occurs.
    """
    loc = Locale.normalize(language)
    result = list(items)
    if path:
        needle = normalize_filter(path)
        result = [
            item
            for item in result
            if normalize_filter(item.base_type) == needle or normalize_filter(item.path) == needle
        ]
    if rarity is not None:
        result = [item for item in result if item.stars == rarity]
    if search:
        result = [item for item in result if matches_text(item, search, loc)]
    return result

def sort_lightcones(
    items: Iterable[LightConeSummary],
    *,
    sort_by: str,
    ascending: bool,
    locale: Locale | str,
) -> list[LightConeSummary]:
    """Order light cones by ID, rarity, localized name, or ATK.

    Unknown sort_by values use ID; ascending=False reverses the ordering. No IO occurs.
    """
    loc = Locale.normalize(locale)
    keys = {
        "id": lambda item: item.id,
        "rarity": lambda item: (item.stars or 0, item.id),
        "name": lambda item: (item.display_name(loc) or "").casefold(),
        "atk": lambda item: (item.atk or 0, item.id),
    }
    return sorted(items, key=keys.get(sort_by, keys["id"]), reverse=not ascending)

def filter_relics(
    items: Iterable[RelicSetSummary], *, search: str | None, language: Locale | str
) -> list[RelicSetSummary]:
    """Copy relic sets matching localized search, or copy all entries when empty."""
    if not search:
        return list(items)
    loc = Locale.normalize(language)
    return [item for item in items if matches_text(item, search, loc)]

def filter_monsters(
    items: Iterable[MonsterSummary],
    *,
    rank: str | None,
    weakness: str | None,
    search: str | None,
    language: Locale | str,
) -> list[MonsterSummary]:
    """Copy monsters matching normalized rank/weakness and localized search.

    None filters are ignored; language accepts Locale aliases. No IO occurs.
    """
    result = list(items)
    if rank:
        needle = normalize_filter(rank)
        result = [item for item in result if normalize_filter(item.rank) == needle]
    if weakness:
        needle = normalize_filter(weakness)
        result = [
            item for item in result if any(normalize_filter(weak) == needle for weak in item.weak)
        ]
    if search:
        result = [item for item in result if matches_text(item, search, Locale.normalize(language))]
    return result

def filter_items(
    items: Iterable[ItemSummary],
    *,
    search: str | None,
    category: str | None,
    rarity: int | None = None,
) -> list[ItemSummary]:
    """Copy items matching category, rarity, and name/description search.

    Category compares either main or sub type; comparisons are case-insensitive.
    None filters are ignored and the helper performs no IO.
    """
    result = list(items)
    if category:
        needle = normalize_filter(category)
        result = [
            item
            for item in result
            if normalize_filter(item.item_main_type) == needle
            or normalize_filter(item.item_sub_type) == needle
        ]
    if rarity is not None:
        result = [item for item in result if item.stars == rarity]
    if search:
        needle = search.casefold()
        result = [
            item
            for item in result
            if needle in (item.item_name or "").casefold()
            or needle in (item.item_desc or "").casefold()
        ]
    return result

def filter_named(items: Iterable[Any], search: str | None) -> list[Any]:
    """Copy entries whose name contains search case-insensitively, or all when empty."""
    if not search:
        return list(items)
    needle = search.casefold()
    return [item for item in items if needle in (getattr(item, "name", "") or "").casefold()]

def skill_icon_suffix(skill: Any) -> str | None:
    """Return the CDN icon suffix for a standard skill type, or None if unsupported."""
    mapping = {
        "Basic ATK": "Normal",
        "Skill": "BP",
        "Ultimate": "Ultra",
        "Technique": "Maze",
        "Talent": "Passive",
    }
    return mapping.get(skill.type_name)

def resolve_asset_path(value: str, specs: dict[str, str]) -> str | None:
    """Resolve an asset alias, game path, filename, or numeric avatar ID.

    Prefer entries in specs, then known CDN path conversions. Return None for
    unrecognized values. This pure resolution helper does not download an asset.
    """
    if not value:
        return None
    normalized = value.replace("\\", "/").strip()
    if normalized.startswith("asset:"):
        normalized = normalized[6:]
    filename = normalized.split("/")[-1]
    stem = Path(filename).stem
    candidates = [
        normalized,
        value,
        f"stem:{stem}",
        f"avatar:{stem}",
        f"character:{stem}",
        f"lightcone:{stem}",
        f"relic:{stem}",
        f"monster:{stem}",
        f"item:{stem}",
        f"element:{stem.lower()}",
        f"path:{stem.lower()}",
    ]
    if ":" in normalized:
        candidates.insert(0, normalized)
    for key in candidates:
        if key in specs:
            return specs[key]
    lower = normalized.lower()
    if lower.startswith("spriteoutput/monsterfigure/"):
        return f"monstermiddleicon/{stem}.webp"
    if lower.startswith("spriteoutput/item"):
        return f"itemfigures/{stem}.webp"
    if lower.endswith((".webp", ".png", ".jpg", ".jpeg")):
        return normalized
    if normalized.isdigit():
        return f"avatarshopicon/{normalized}.webp"
    return None

__all__ = ['matches_text', 'normalize_filter', 'apply_extra_filters', '_filter_characters', 'sort_characters', 'filter_lightcones', 'sort_lightcones', 'filter_relics', 'filter_monsters', 'filter_items', 'filter_named', 'skill_icon_suffix', 'resolve_asset_path']
