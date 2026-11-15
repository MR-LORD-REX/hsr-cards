"""Public result objects for one endgame season and its floor images."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from PIL import Image
from ...core.types import GameMode


@dataclass
class EndgameFloorCard:
    """One floor image with its source stage and optional rendered-cache path."""

    image: Image.Image
    floor: int
    stage_id: int | None = None
    name: str | None = None
    cache_path: Path | None = None

    def save(self, *args, **kwargs):
        """Save the image using the arguments accepted by PIL.Image.save."""
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name: str):
        """Forward unresolved attributes, such as size, to this floor card's PIL image."""
        return getattr(self.image, name)


@dataclass
class EndgameCardResult:
    """A season's floor cards and authoritative live-window metadata."""

    game_mode: GameMode
    season_id: int
    season_name: str
    version: str
    cards: list[EndgameFloorCard] = field(default_factory=list)
    begins_at: datetime | None = None
    ends_at: datetime | None = None
    is_live: bool = False
    next_season_id: int | None = None

    @property
    def images(self) -> list[Image.Image]:
        """Return floor images in the same order as cards without copying the PIL images."""
        return [card.image for card in self.cards]

    @property
    def start(self) -> datetime | None:
        """Return begins_at as the compatibility start alias, or None for an undated season."""
        return self.begins_at

    @property
    def end(self) -> datetime | None:
        """Return ends_at as the compatibility end alias, or None for an undated season."""
        return self.ends_at
