"""Item summaries and grouped achievement models."""
from __future__ import annotations
from typing import Any
from pydantic import Field, computed_field

from .common import NamedEntry, NanokaModel, parse_rarity, snake_case

class ItemSummary(NanokaModel):
    """An item catalog entry with category, rarity, icons, lore, and source metadata.

    Numeric id is required; from_entry() normalizes provider PascalCase keys.
    Absent optional item fields remain None and unknown fields are retained.
    """
    id: int
    item_name: str | None = None
    item_sub_type: str | None = None
    item_main_type: str | None = None
    purpose_type: int | None = None
    rarity: str | None = None
    item_icon_path: str | None = None
    item_figure_icon_path: str | None = None
    item_currency_icon_path: str | None = None
    item_avatar_icon_path: str | None = None
    item_desc: str | None = None
    item_bg_desc: str | None = None
    item_comefrom: list[NamedEntry] = Field(default_factory=list)
    pile_limit: int | None = None

    @computed_field
    @property
    def name(self) -> str | None:
        """Return the localized item_name field supplied by the catalog."""
        return self.item_name

    @computed_field
    @property
    def desc(self) -> str | None:
        """Return background lore when available, otherwise the item description."""
        return self.item_bg_desc or self.item_desc

    @computed_field
    @property
    def stars(self) -> int | None:
        """Return numeric rarity stars, or None when the provider rarity is unknown."""
        return parse_rarity(self.rarity)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "ItemSummary":
        """Parse a provider catalog entry with a numeric identifier into this model.

        PascalCase keys are normalized to snake_case. Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        normalized = {snake_case(key): value for key, value in payload.items()}
        normalized.setdefault("id", int(identifier))
        return cls.model_validate(normalized)

class Achievement(NanokaModel):
    """One achievement with its numeric ID, text, rarity, visibility, and parameters."""
    id: int
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    show_type: str | None = None
    param_list: list[float | int] = Field(default_factory=list)

class AchievementSeries(NanokaModel):
    """A prioritized achievement group whose provider list field contains achievements.

    Numeric id is required; items/count expose the parsed collection without
    fetching individual achievements.
    """
    id: int
    priority: int | None = None
    name: str | None = None
    achievements: list[Achievement] = Field(default_factory=list, alias="list")

    @computed_field
    @property
    def items(self) -> list[Achievement]:
        """Return the achievement models contained in this series."""
        return self.achievements

    @computed_field
    @property
    def count(self) -> int:
        """Return the number of achievements in this series."""
        return len(self.achievements)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "AchievementSeries":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

__all__ = ['ItemSummary', 'Achievement', 'AchievementSeries']
