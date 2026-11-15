"""Resolve character versions and cached assets into info renderer models."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import aggregate
from hsr_cards.renderer.nanoka.character_info import bonus_stats
from hsr_cards.renderer.nanoka.character_info import clean_localized
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.character_info import max_stats
from hsr_cards.renderer.nanoka.character_info import skill_materials
from hsr_cards.renderer.nanoka.data import CharacterData
from hsr_cards.renderer.nanoka.data import load_character
from hsr_cards.renderer.nanoka.data import prime_assets
from pathlib import Path
from hsr_cards.renderer.nanoka.info.models import CardData
from hsr_cards.renderer.nanoka.info.styles import ELEMENT_LABELS, PATH_LABELS


async def load_data(
    character_id: int | str,
    locale: str,
    *,
    version: str | None = None,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[CardData, CharacterData]:
    """Load a character ID/name and prepare the resolved info-card model.

    version=None selects the newest build; locale selects Nanoka's language.
    cache_dir/proxy configure provider storage/requests. Return (CardData,
    CharacterData), transferring the data client's cleanup to the caller on success.
    Catalog/detail/artwork requests may write the provider cache; loading/preparation
    errors propagate and close the operation-created client.
    """
    character = await load_character(
        character_id,
        version=version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
    )
    try:
        return await build_card_data(character), character
    except BaseException:
        await character.client.close()
        raise


async def build_card_data(character: CharacterData) -> CardData:
    """Prepare identity, level-80 stats, bonuses and material totals for a character.

    Return CardData containing decoded artwork and cached icon paths for this
    CharacterData's version/locale. Fetch only required provider assets; missing
    optional icons remain absent. Provider/model/image errors propagate. The supplied
    character client is borrowed and remains open for its owner.
    """
    detail = character.detail
    locale = character.locale
    character_id = character.character_id
    icons: dict[int, Path | None] = {}
    relatives = [f"itemfigures/2.webp"]
    for stat in detail.stats.values():
        for cost in stat.cost:
            relatives.append(f"itemfigures/{cost.item_id}.webp")
    for trace in detail.traces:
        for level in trace.levels:
            for cost in level.material_list:
                relatives.append(f"itemfigures/{cost.item_id}.webp")
    relatives.extend(
        [
            f"avatardrawcard/{character_id}.webp",
            f"element/{character.element}.webp",
            f"pathicon/{character.path}.webp",
        ]
    )
    await prime_assets(character, relatives)
    asset_root = character.client.cache.asset_file("")
    for stat in detail.stats.values():
        for cost in stat.cost:
            icons[cost.item_id] = asset_root / "itemfigures" / f"{cost.item_id}.webp"
    for trace in detail.traces:
        for level in trace.levels:
            for cost in level.material_list:
                icons[cost.item_id] = icons.get(cost.item_id) or asset_root / "itemfigures" / f"{cost.item_id}.webp"

    asset_root = character.client.cache.asset_file("")
    for item_id, path in icons.items():
        if path is None or not path.is_file():
            fallback = asset_root / "itemfigures" / f"{item_id}.webp"
            icons[item_id] = fallback if fallback.is_file() else None

    element = character.element
    path_code = character.path
    data = CardData(
        character_id=character_id,
        locale=locale,
        version=character.version,
        name=clean_localized(character.name, locale) or str(character_id),
        desc=clean_localized(character.description, locale),
        stars=character.stars,
        detail=detail,
        items=character.items,
        stats=max_stats(detail),
        bonuses=bonus_stats(detail, locale),
        sp_need=detail.sp_need,
        icon_dir=asset_root / "skillicons",
        ascension=aggregate([cost for stat in detail.stats.values() for cost in stat.cost]),
        skills=skill_materials(detail),
        icons=icons,
        splash=load_webp(asset_root / "avatardrawcard" / f"{character_id}.webp"),
        element_icon=load_webp(asset_root / "element" / f"{element}.webp"),
        path_icon=load_webp(asset_root / "pathicon" / f"{path_code}.webp"),
        element_label=ELEMENT_LABELS.get(locale, ELEMENT_LABELS["en"]).get(element, element.title()),
        path_label=PATH_LABELS.get(locale, PATH_LABELS["en"]).get(path_code, (detail.path or "").title()),
    )
    return data


async def build_comparison_card_data(
    identifier: int | str,
    from_version: str,
    to_version: str,
    locale: str = "en",
    *,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[CardData, CharacterData, CharacterData]:
    """Prepare one info-card comparison from ordered older/newer Nanoka builds.

    identifier accepts a numeric ID or published name; locale defaults to en and
    cache_dir/proxy configure downloads. Return (newer CardData, older CharacterData,
    newer CharacterData), attaching the older model and merging icon lookups.

    Both data clients remain caller-owned on success and must be closed. Loading or
    preparation failures propagate after releasing created clients. This function
    loads/cache assets but does not render or save generated images.
    """
    before_character = await load_character(
        identifier, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy
    )
    try:
        after_character = await load_character(
            identifier, version=to_version, locale=locale, cache_dir=cache_dir, proxy=proxy
        )
    except BaseException:
        await before_character.client.close()
        raise
    try:
        before = await build_card_data(before_character)
        after = await build_card_data(after_character)
    except BaseException:
        await before_character.client.close()
        await after_character.client.close()
        raise
    after.before = before
    after.icons = {**before.icons, **after.icons}
    return after, before_character, after_character
