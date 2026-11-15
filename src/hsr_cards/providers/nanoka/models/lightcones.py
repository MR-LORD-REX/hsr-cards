"""Light-cone summaries, refinements, and promotion stats."""
from __future__ import annotations
from typing import Any
from pydantic import Field, computed_field
from ..locales import DEFAULT_LOCALE, Locale

from .common import MaterialCost, NanokaModel, localized_field, normalize_path, normalize_path_codename, parse_rarity

class LightConeSummary(NanokaModel):
    """A light-cone catalog identity with multilingual names, path, rarity, and ATK.

    Numeric id is required and baseType is accepted as the provider path alias.
    """
    id: int
    rank: str | None = None
    base_type: str | None = Field(default=None, alias="baseType")
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    atk: float | int | None = None
    desc: str | None = None

    @computed_field
    @property
    def name(self) -> str | None:
        """Return the English display name with other-language fallback, or None."""
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def stars(self) -> int | None:
        """Return numeric rarity stars, or None when the provider rarity is unknown."""
        return parse_rarity(self.rank)

    @computed_field
    @property
    def path(self) -> str | None:
        """Return the normalized display path, or None when no path is supplied."""
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        """Return the normalized provider path codename, or None if absent."""
        return normalize_path_codename(self.base_type)

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        """Return the requested locale name with optional en/zh/ja/ko fallback.

        Locale aliases are accepted. Return None if absent; invalid aliases raise
        ValueError. Game ruby markup is removed without performing IO.
        """
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "LightConeSummary":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class RefinementLevel(NanokaModel):
    """One superimposition level and its published effect parameter array."""
    level: int | None = None
    param_list: list[float | int] = Field(default_factory=list)

class LightConeRefinement(NanokaModel):
    """A light-cone effect description with parameters for each superimposition level.

    Provider string keys are retained; levels exposes numeric keys for valid entries.
    """
    name: str | None = None
    desc: str | None = None
    level: dict[str, RefinementLevel] = Field(default_factory=dict)

    @computed_field
    @property
    def levels(self) -> dict[int, list[float | int]]:
        """Return refinement parameters keyed by numeric superimposition level."""
        return {
            int(key): value.param_list
            for key, value in self.level.items()
            if str(key).isdigit()
        }

class PromotionCost(MaterialCost):
    """A light-cone promotion material ID and quantity using the shared cost schema."""
    pass

class LightConeStat(NanokaModel):
    """A light-cone promotion stat block with level gates, base/additive stats, and costs.

    The required equipment_id identifies the cone; optional fields retain missing
    data rather than calculating a character-specific contribution.
    """
    equipment_id: int
    promotion: int | None = None
    promotion_cost_list: list[PromotionCost] = Field(default_factory=list)
    player_level_require: int | None = None
    world_level_require: int | None = None
    max_level: int | None = None
    base_hp: float | None = None
    base_hp_add: float | None = None
    base_attack: float | None = None
    base_attack_add: float | None = None
    base_defence: float | None = None
    base_defence_add: float | None = None

class LightConeDetail(NanokaModel):
    """A light-cone detail document with effect refinements and promotion stat blocks."""
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    base_type: str | None = None
    refinements: LightConeRefinement | None = None
    stats: list[LightConeStat] = Field(default_factory=list)

    @computed_field
    @property
    def stars(self) -> int | None:
        """Return numeric rarity stars, or None when the provider rarity is unknown."""
        return parse_rarity(self.rarity)

    @computed_field
    @property
    def path(self) -> str | None:
        """Return the normalized display path, or None when no path is supplied."""
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        """Return the normalized provider path codename, or None if absent."""
        return normalize_path_codename(self.base_type)

__all__ = ['LightConeSummary', 'RefinementLevel', 'LightConeRefinement', 'PromotionCost', 'LightConeStat', 'LightConeDetail']
