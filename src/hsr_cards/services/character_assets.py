"""Cache-relative character artwork names and targeted asset preparation."""
from __future__ import annotations
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .character_data import CharacterData
RANK_ASSET_DIR = "rank/_dependencies/textures"


def skill_icon_relative(character_id: int, suffix: str) -> str:
    """Return the CDN-relative webp path for a character ID and skill suffix; no IO occurs."""
    return f"skillicons/SkillIcon_{character_id}_{suffix}.webp"


def rank_texture_relative(character_id: int, rank: int | str) -> str:
    """Return the dependency-texture path for a character ID and eidolon rank; no IO occurs."""
    return f"{RANK_ASSET_DIR}/{character_id}/{character_id}_Rank_{rank}.webp"


def rank_icon_relative(rank_icon: str | None) -> str | None:
    """Map a Nanoka ``SkillIcon_1415_Rank1.png`` icon path to its webp."""
    if not rank_icon:
        return None
    stem = Path(str(rank_icon).replace("\\", "/")).stem
    return f"skillicons/{stem}.webp" if stem else None


def drawcard_relative(character_id: int | str) -> str:
    """Return the CDN-relative splash-art path for a numeric character ID."""
    return f"avatardrawcard/{character_id}.webp"


def element_relative(element: str | None) -> str | None:
    """Return an element icon path, or None for an empty element codename."""
    return f"element/{element}.webp" if element else None


def path_relative(path: str | None) -> str | None:
    """Return a path icon path, or None for an empty path codename."""
    return f"pathicon/{path}.webp" if path else None


def item_relative(item_id: int | str) -> str:
    """Return the CDN-relative material/item icon path for an item ID."""
    return f"itemfigures/{item_id}.webp"


async def prime_assets(character: CharacterData, relatives: Sequence[str]) -> dict[str, Path]:
    """Fetch unique, nonempty CDN-relative asset paths through the supplied character.

    Return relative-path-to-local-Path entries only for resolved assets. Downloads may
    write this character's provider cache; provider failures propagate. The supplied
    character/client remains caller-owned and is not closed.
    """
    result: dict[str, Path] = {}
    for relative in dict.fromkeys(item for item in relatives if item):
        path = await character.asset(relative)
        if path is not None:
            result[relative] = path
    return result
