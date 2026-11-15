"""Load version-aware character data and prepare resolved skills render models."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import bonus_stats
from hsr_cards.renderer.nanoka.character_info import clean_localized
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.character_info import max_stats
from hsr_cards.renderer.nanoka.data import CharacterData
from hsr_cards.renderer.nanoka.data import load_character
from hsr_cards.renderer.nanoka.data import prime_assets
from hsr_cards.renderer.nanoka.data import rank_icon_relative
from hsr_cards.renderer.nanoka.data import rank_texture_relative
from pathlib import Path
from hsr_cards.renderer.nanoka.skills.comparison import mark_skill_diff
from hsr_cards.renderer.nanoka.skills.models import SkillData, SkillsCardResult
from hsr_cards.renderer.nanoka.skills.preparation import plain, rank_rows, skill_groups
from hsr_cards.renderer.nanoka.skills.rendering import render_full
from hsr_cards.renderer.nanoka.skills.styles import ELEMENT_LABELS, PATH_LABELS


async def load_data(
    character_id: int | str,
    locale: str,
    *,
    version: str | None = None,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[SkillData, CharacterData]:
    """Load a character ID/name and prepare a SkillData renderer model.

    version=None selects the newest Nanoka build. locale/cache_dir/proxy configure
    language, provider storage and requests. Return (SkillData, CharacterData);
    the caller must close the returned data client. Loading/preparation may cache
    catalogs/assets; failures propagate after closing operation-created resources.
    """
    character = await load_character(
        character_id,
        version=version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
    )
    try:
        return await build_skill_data(character), character
    except BaseException:
        await character.client.close()
        raise


async def build_skill_data(character: CharacterData) -> SkillData:
    """Prepare skills, eidolons, stats, glossary entries and artwork for one character.

    Return SkillData for the supplied CharacterData's version/locale, fetching only
    required icons/rank textures into its provider cache. Missing optional artwork
    remains absent. Provider/model/image errors propagate; the supplied client stays
    borrowed and is not closed or replaced.
    """
    detail = character.detail
    locale = character.locale
    character_id = character.character_id
    record = character.catalog_record
    description = plain(character.description)
    element = character.element
    path = character.path
    element_labels = ELEMENT_LABELS.get(locale, ELEMENT_LABELS["en"])
    path_labels = PATH_LABELS.get(locale, PATH_LABELS["en"])
    memosprite = detail.memosprite or {}
    spprite_name = clean_localized(str(memosprite.get("name") or ""), locale) or ""
    spprite_icon = Path(str(memosprite.get("icon") or "")).stem
    spprite_code = "".join(ch for ch in spprite_icon if ch.isdigit())

    relatives = [
        f"avatardrawcard/{character_id}.webp",
        f"element/{element}.webp",
        f"pathicon/{path}.webp",
    ]
    for icon in (
        "IconMaxHP",
        "IconAttack",
        "IconDefence",
        "IconSpeed",
        "IconCriticalChance",
        "IconCriticalDamage",
        "IconFireAddedRatio",
        "IconIceAddedRatio",
        "IconWindAddedRatio",
        "IconThunderAddedRatio",
        "IconPhysicalAddedRatio",
        "IconQuantumAddedRatio",
        "IconImaginaryAddedRatio",
    ):
        relatives.append(f"skillicons/{icon}.webp")
    for suffix in ("Normal", "BP", "Ultra", "Passive", "Maze"):
        relatives.append(f"skillicons/SkillIcon_{character_id}_{suffix}.webp")
    if spprite_code:
        relatives.extend(
            [
                f"skillicons/SkillIcon_{spprite_code}_Servant.webp",
                f"skillicons/SkillIcon_{spprite_code}_ServantPassive.webp",
            ]
        )
    ranks = rank_rows(detail.ranks)
    for rank in ranks:
        icon = rank_icon_relative(rank.rank.icon)
        if icon:
            relatives.append(icon)
    await prime_assets(character, relatives)

    rank_dir = None
    if ranks:
        first_rank = await character.asset(rank_texture_relative(character_id, ranks[0].key))
        for rank in ranks:
            await character.asset(rank_texture_relative(character_id, rank.key))
        if first_rank is not None:
            rank_dir = first_rank.parent

    data = SkillData(
        character_id=character_id,
        locale=locale,
        version=character.version,
        name=clean_localized(character.name, locale) or str(character_id),
        description=description,
        element_label=element_labels.get(element, element.title()),
        path_label=path_labels.get(path, (detail.path or "").title()),
        stars=character.stars,
        splash=load_webp(character.client.cache.asset_file(f"avatardrawcard/{character_id}.webp")),
        element_icon=load_webp(character.client.cache.asset_file(f"element/{element}.webp")),
        path_icon=load_webp(character.client.cache.asset_file(f"pathicon/{path}.webp")),
        skill_icon_dir=character.client.cache.asset_file("skillicons"),
        rank_icon_dir=rank_dir,
        skills=skill_groups(detail),
        eidolons=ranks,
        memosprite_name=spprite_name,
        memosprite_code=spprite_code,
        detail=detail,
        stats=max_stats(detail),
        bonuses=bonus_stats(detail, locale),
        sp_need=detail.sp_need or 0,
        items=character.items,
    )
    return data


async def build_comparison_data(
    character_id: int | str,
    from_version: str,
    to_version: str,
    locale: str = "en",
    *,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[SkillData, CharacterData, CharacterData]:
    """Prepare skills/eidolon changes between ordered older/newer Nanoka builds.

    character_id accepts a numeric ID or published name; locale defaults to en and
    cache_dir/proxy configure data requests. Return (newer SkillData, older
    CharacterData, newer CharacterData) with changed runs and previous stats attached.

    Both data clients transfer to the caller on success. Loading/preparation failures
    propagate after created clients are closed. No generated image cache is read or
    written by this preparation step.
    """
    before_data = await load_character(
        character_id, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy
    )
    try:
        after_data = await load_character(
            character_id, version=to_version, locale=locale, cache_dir=cache_dir, proxy=proxy
        )
    except BaseException:
        await before_data.client.close()
        raise
    try:
        before = await build_skill_data(before_data)
        after = await build_skill_data(after_data)
    except BaseException:
        await before_data.client.close()
        await after_data.client.close()
        raise
    mark_skill_diff(before, after)
    after.version_before = before.version
    after.version_after = after.version
    after.stats_before = before.stats
    after.bonuses_before = before.bonuses
    after.sp_need_before = before.sp_need
    return after, before_data, after_data


async def build_skills_card(
    character_id: int | str,
    locale: str = "en",
    *,
    version: str | None = None,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> SkillsCardResult:
    """Load one character ID/name and render its full skills/eidolon sheet.

    version=None selects the newest build; locale defaults to en and cache_dir/proxy
    configure provider data. Return SkillsCardResult with image, tables, dropdowns
    and sections. Catalog/asset requests may write provider caches; no generated
    image is saved here. Errors propagate and the operation-owned client is closed.
    """
    data, character = await load_data(
        character_id, locale, version=version, cache_dir=cache_dir, proxy=proxy
    )
    try:
        return render_full(data)
    finally:
        await character.client.close()
