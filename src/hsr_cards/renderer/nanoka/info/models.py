"""Resolved character identity, material costs, stats, and comparison text."""
from __future__ import annotations

from PIL import Image
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DetailPiece:
    """One laid-out identity-description segment with RGBA color and optional removal strikethrough."""
    text: str
    color: tuple[int, int, int, int]
    strike: bool = False


@dataclass
class CardData:
    """Resolved character identity, stats, materials and cached artwork with an optional older comparison model."""
    character_id: int
    locale: str
    version: str
    name: str
    desc: str
    stars: int
    detail: Any
    items: dict[str, Any]
    stats: dict[str, float]
    bonuses: list[tuple[str, float, str]]
    sp_need: int | None
    icon_dir: Path | None
    ascension: list[Any]
    skills: list[Any]
    icons: dict[int, Path | None]
    splash: Image.Image | None
    element_icon: Image.Image | None
    path_icon: Image.Image | None
    element_label: str
    path_label: str
    before: "CardData | None" = None

    @property
    def comparison(self) -> bool:
        """Return whether an older info-card model is attached for inline comparison."""
        return self.before is not None
