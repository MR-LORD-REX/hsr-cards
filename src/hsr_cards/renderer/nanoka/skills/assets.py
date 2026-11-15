"""Read cached skill and eidolon artwork without performing network requests."""
from __future__ import annotations

from PIL import Image
from hsr_cards.renderer.nanoka.character_info import load_webp
from pathlib import Path
from hsr_cards.renderer.nanoka.skills.models import RankRow, SkillData, SkillGroup


def skill_icon(data: SkillData, group: SkillGroup, size: int) -> Image.Image | None:
    """Read and resize a cached character/memosprite skill icon to size square pixels; unavailable artwork returns None."""
    code = data.memosprite_code if group.scope == "memosprite" else str(data.character_id)
    suffix = group.icon_code or ""
    if group.scope == "memosprite" and suffix == "Passive":
        suffix = "ServantPassive"
    elif group.scope == "memosprite":
        suffix = "Servant"
    if not code or not suffix:
        return None
    candidates = (f"SkillIcon_{code}_{suffix}.webp", f"SkillIcon_{code}_Servant.webp", f"SkillIcon_{code}_Servant01.webp")
    for name in candidates:
        image = load_webp(data.skill_icon_dir / name, (size, size))
        if image:
            return image
    return None


def rank_portrait(path: Path, size: int) -> Image.Image | None:
    """Read a cached RGBA eidolon portrait, trim transparent margins and crop/resize to a square; missing artwork returns None."""
    image = load_webp(path)
    if image is None:
        return None
    alpha = image.getchannel("A").point(lambda value: 255 if value > 30 else 0)
    box = alpha.getbbox()
    if box:
        image = image.crop(box)
    side = min(image.width, image.height)
    left = max(0, (image.width - side) // 2)
    top = max(0, round(image.height * 0.06))
    if top + side > image.height:
        top = image.height - side
    image = image.crop((left, max(0, top), left + side, max(0, top) + side))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def eidolon_icon(data: SkillData, rank: RankRow, size: int) -> Image.Image | None:
    # Nanoka points E3/E5 at the generic Ultra/Skill icons, so prefer real
    # rank textures when they were downloaded into the card cache.
    """Read a size-square eidolon icon, preferring rank portraits over Nanoka generic-icon fallbacks; no network occurs."""
    if data.rank_icon_dir:
        image = rank_portrait(data.rank_icon_dir / f"{data.character_id}_Rank_{rank.key}.webp", size)
        if image:
            return image
    candidates = [f"SkillIcon_{data.character_id}_Rank{rank.key}.webp"]
    stem = Path(rank.rank.icon or "").stem
    if stem:
        candidates.append(f"{stem}.webp")
    for name in candidates:
        image = load_webp(data.skill_icon_dir / name, (size, size))
        if image:
            return image
    return None


def previous_rank(data: SkillData, rank: RankRow) -> RankRow | None:
    """Return the preceding eidolon in data order, or None for the first/unlisted rank."""
    keys = [item.key for item in data.eidolons]
    try:
        index = keys.index(rank.key)
    except ValueError:
        return None
    return data.eidolons[index - 1] if index > 0 else None


def previous_eidolon_icon(data: SkillData, rank: RankRow, size: int) -> Image.Image | None:
    """The previous eidolon's skill icon, shown top-left on each card.

    Nanoka only publishes Rank1/2/4/6 skill icons; E3 and E5 point at the
    generic Ultra/Skill icons. Reading the previous rank's own ``icon`` field
    keeps that mapping intact. E1 has no predecessor, so it falls back to the
    character's basic ATK icon.
    """
    before = previous_rank(data, rank)
    if before is not None:
        icon_name = Path(str(before.rank.icon or "")).stem
        candidates = [f"{icon_name}.webp"] if icon_name else []
        candidates.append(f"SkillIcon_{data.character_id}_Rank{before.key}.webp")
        for name in candidates:
            image = load_webp(data.skill_icon_dir / name, (size, size))
            if image:
                return image
        if data.rank_icon_dir:
            image = rank_portrait(
                data.rank_icon_dir / f"{data.character_id}_Rank_{before.key}.webp", size
            )
            if image:
                return image
    for suffix in ("Normal", "BP", "Ultra"):
        image = load_webp(
            data.skill_icon_dir / f"SkillIcon_{data.character_id}_{suffix}.webp", (size, size)
        )
        if image:
            return image
    return None
