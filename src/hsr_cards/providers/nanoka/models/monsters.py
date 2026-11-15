"""Monster summaries, variants, and difficulty-scaling models."""
from __future__ import annotations
from typing import Any
from pydantic import Field, computed_field
from ..locales import DEFAULT_LOCALE, Locale

from .common import NanokaModel, localized_field

class MonsterSummary(NanokaModel):
    """A catalog monster identity with multilingual names, rank, weaknesses, and variant IDs.

    Numeric id is required; child IDs link stage variants to their catalog base
    monster without resolving or loading detail documents.
    """
    id: int
    rank: str | None = None
    camp: int | None = None
    icon: str | None = None
    child: list[int] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    desc: str | None = None

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        """Return the requested locale name with optional en/zh/ja/ko fallback.

        Locale aliases are accepted. Return None if absent; invalid aliases raise
        ValueError. Game ruby markup is removed without performing IO.
        """
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @computed_field
    @property
    def name(self) -> str | None:
        """Return the English display name with other-language fallback, or None."""
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def weaknesses(self) -> list[str]:
        """Return lowercase weakness elements, or [] when no weaknesses exist."""
        return [weakness.lower() for weakness in self.weak]

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "MonsterSummary":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class MonsterStats(NanokaModel):
    """A numeric monster base-stat record from the provider scaling catalog.

    Accept the provider PascalCase stat aliases. Stage, difficulty, phase, and
    corrosion multipliers are applied by services rather than this data model.
    """
    id: int | None = None
    rank: str | None = Field(default=None, alias="Rank")
    attack_base: float | int | None = Field(default=None, alias="AttackBase")
    defence_base: float | int | None = Field(default=None, alias="DefenceBase")
    hp_base: float | int | None = Field(default=None, alias="HPBase")
    speed_base: float | int | None = Field(default=None, alias="SpeedBase")
    stance_base: float | int | None = Field(default=None, alias="StanceBase")
    status_resistance_base: float | None = Field(default=None, alias="StatusResistanceBase")
    child: list[dict[str, Any]] = Field(default_factory=list)

class EliteGroup(NanokaModel):
    """An elite-group ID and its ATK/DEF/HP/speed/toughness scaling ratios.

    Ratios default to one when omitted and accept provider PascalCase aliases.
    """
    elite_group: int = Field(alias="EliteGroup")
    attack_ratio: float = Field(default=1, alias="AttackRatio")
    defence_ratio: float = Field(default=1, alias="DefenceRatio")
    hp_ratio: float = Field(default=1, alias="HPRatio")
    speed_ratio: float = Field(default=1, alias="SpeedRatio")
    stance_ratio: float = Field(default=1, alias="StanceRatio")

class HardLevelGroup(NanokaModel):
    """Difficulty-group and monster-level scaling ratios with combat-power metadata.

    The group ID and level are required; omitted ratios default to one. This
    model supplies factors without calculating final encounter stats.
    """
    hard_level_group: int = Field(alias="HardLevelGroup")
    level: int = Field(alias="Level")
    attack_ratio: float = Field(default=1, alias="AttackRatio")
    defence_ratio: float = Field(default=1, alias="DefenceRatio")
    hp_ratio: float = Field(default=1, alias="HPRatio")
    speed_ratio: float = Field(default=1, alias="SpeedRatio")
    stance_ratio: float = Field(default=1, alias="StanceRatio")
    combat_power_list: list[float | int] = Field(default_factory=list, alias="CombatPowerList")

class InfiniteEliteGroup(EliteGroup):
    """The PF infinite-wave specialization of the shared elite scaling-ratio model."""
    pass

class MonsterVariant(NanokaModel):
    """A stage monster variant with stat modifiers, weaknesses, resistances, and skills.

    Numeric id is required. Group references and optional ratios/flat values remain
    unapplied until an encounter service resolves the stage context.
    """
    id: int
    attack_modify_ratio: float | None = None
    defence_modify_ratio: float | None = None
    elite_group: int | None = None
    hp_modify_ratio: float | None = None
    speed_modify_ratio: float | None = None
    speed_modify_value: float | None = None
    stance_modify_ratio: float | None = None
    stance_modify_value: float | None = None
    stance_weak_list: list[str] = Field(default_factory=list)
    hard_level_group: int | None = None
    damage_type_resistance: list[dict[str, Any]] = Field(default_factory=list)
    skill_list: list[dict[str, Any] | int] = Field(default_factory=list)

class MonsterDetail(NanokaModel):
    """A monster detail document with base combat stats, variant records, art, and drops.

    Numeric id is required; weaknesses exposes the first variant weakness list.
    Final stage HP and phase behavior are resolved outside this model.
    """
    id: int
    name: str | None = None
    desc: str | None = None
    monster_camp_id: int | None = None
    attack_base: float | None = None
    critical_damage_base: float | None = None
    defence_base: float | None = None
    hp_base: float | None = None
    initial_delay_ratio: float | None = None
    image_path: str | None = None
    minimum_fatigue_ratio: float | None = None
    rank: str | None = None
    speed_base: float | None = None
    stance_base: float | None = None
    stance_count: int | None = None
    status_resistance_base: float | None = None
    child: list[MonsterVariant] = Field(default_factory=list)
    drop: list[Any] = Field(default_factory=list)

    @computed_field
    @property
    def weaknesses(self) -> list[str]:
        """Return lowercase weaknesses from the first monster variant, or [] if absent."""
        if self.child:
            return [weakness.lower() for weakness in self.child[0].stance_weak_list]
        return []

    @computed_field
    @property
    def variants(self) -> list[MonsterVariant]:
        """Return the published monster variant models."""
        return self.child

__all__ = ['MonsterSummary', 'MonsterStats', 'EliteGroup', 'HardLevelGroup', 'InfiniteEliteGroup', 'MonsterVariant', 'MonsterDetail']
