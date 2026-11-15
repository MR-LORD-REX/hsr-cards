"""Currency Wars roles, traits, items, buffs, and augments."""
from __future__ import annotations
from typing import Any
from pydantic import Field

from .common import NanokaModel, snake_case

class CurrencyRole(NanokaModel):
    """A Currency Wars role with rarity, combat position, charges, and trait IDs."""
    id: int
    name: str | None = None
    front_back_type: str | None = None
    rarity: int | None = None
    heal_or_shield_display: str | None = None
    charge_type: list[str] = Field(default_factory=list)
    max_sp_icon: str | None = None
    trait_list: list[int] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyRole":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class CurrencyTraitLayer(NanokaModel):
    """One Currency Wars trait layer with buff text, quality, and effect parameters."""
    id: int | None = None
    buff_name: str | None = None
    buff_desc: str | None = None
    buff_simple_desc: str | None = None
    buff_param_list: list[float | int] = Field(default_factory=list)
    quality: str | None = None
    param_list: list[float | int] = Field(default_factory=list)

class CurrencyTrait(NanokaModel):
    """A Currency Wars trait with activation rules, effects, layers, and related traits.

    Effect collections accept the provider list or mapping shapes; optional
    remark/sub-trait data and unknown fields are retained.
    """
    id: int
    activation_type: str | None = None
    icon_path: str | None = None
    name: str | None = None
    desc: str | None = None
    simple_desc: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    effect_list: list[dict[str, Any] | int] | dict[str, Any] = Field(default_factory=list)
    layer: dict[str, CurrencyTraitLayer] = Field(default_factory=dict)
    remark: dict[str, Any] | None = None
    sub_trait: dict[str, Any] | None = None

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyTrait":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class CurrencyItem(NanokaModel):
    """A Currency Wars item with effect parameters and stacking/consumption rules."""
    id: int
    type: str | None = None
    name: str | None = None
    desc: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    icon_path: str | None = None
    consumable_rule: str | None = None
    if_stack: bool | None = None
    if_consume: bool | None = None

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyItem":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class CurrencyAugment(NanokaModel):
    """A Currency Wars augment with rarity, icon, text, and published effects.

    from_entry() normalizes provider PascalCase keys before validating the model.
    """
    id: int
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    icon: str | None = None
    effect_list: list[Any] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyAugment":
        """Parse a provider catalog entry with a numeric identifier into this model.

        PascalCase keys are normalized to snake_case. Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        normalized = {snake_case(key): value for key, value in payload.items()}
        normalized.setdefault("id", int(identifier))
        return cls.model_validate(normalized)

class CurrencyBuff(NanokaModel):
    """A Currency Wars buff with rarity, icon, text, and description parameters.

    from_entry() normalizes provider PascalCase keys before validating the model.
    """
    id: int
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    icon: str | None = None
    param_list: list[float | int] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyBuff":
        """Parse a provider catalog entry with a numeric identifier into this model.

        PascalCase keys are normalized to snake_case. Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        normalized = {snake_case(key): value for key, value in payload.items()}
        normalized.setdefault("id", int(identifier))
        return cls.model_validate(normalized)

__all__ = ['CurrencyRole', 'CurrencyTraitLayer', 'CurrencyTrait', 'CurrencyItem', 'CurrencyAugment', 'CurrencyBuff']
