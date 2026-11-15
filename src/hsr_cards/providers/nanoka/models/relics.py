"""Relic-set summaries, piece data, and set effects."""
from __future__ import annotations
from typing import Any
from pydantic import Field, computed_field
from ..locales import DEFAULT_LOCALE, Locale

from .common import NanokaModel, RELIC_SLOT_BY_ID, localized_field

class RelicSetEffect(NanokaModel):
    """A relic-set bonus with required piece count, localized text, and parameters.

    Explicit desc takes precedence over language fields; ParamList is accepted as
    the provider parameter alias.
    """
    pieces: int
    desc: str | None = None
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    param_list: list[float | int] = Field(default_factory=list, alias="ParamList")

    def display_desc(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        """Return the explicit description, otherwise localized effect text.

        Locale aliases are accepted; fallback=True tries en/zh/ja/ko. Return None
        when absent and raise ValueError for invalid aliases. No IO occurs.
        """
        return self.desc or localized_field(
            self, locale, "en", "zh", "ja", "ko", fallback=fallback
        )

    @computed_field
    @property
    def description(self) -> str | None:
        """Return the default-language effect description, or None when absent."""
        return self.display_desc()

class RelicSetSummary(NanokaModel):
    """A relic-set catalog identity with multilingual names and piece-count effect groups."""
    id: int
    icon: str | None = None
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    set: dict[str, dict[str, Any]] = Field(default_factory=dict)

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
    def effects(self) -> list[RelicSetEffect]:
        """Return parsed set effects ordered by their required piece count."""
        result: list[RelicSetEffect] = []
        for key in sorted(self.set, key=lambda value: int(value) if str(value).isdigit() else 999):
            payload = dict(self.set[key])
            payload.setdefault("pieces", int(key) if str(key).isdigit() else 0)
            result.append(RelicSetEffect.model_validate(payload))
        return result

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "RelicSetSummary":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class RelicPart(NanokaModel):
    """An individual relic piece with optional ID, name, lore, description, and icon.

    slot resolves known relic slots from the final ID digit without loading assets.
    """
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    story: str | None = None
    icon: str | None = None

    @computed_field
    @property
    def slot(self) -> str | None:
        """Resolve a relic slot from the final item-ID digit, or None if unknown."""
        return RELIC_SLOT_BY_ID.get((self.id or 0) % 10)

class RelicSetEffectDetail(NanokaModel):
    """A detailed set bonus with required piece count, description, and effect parameters."""
    pieces: int
    desc: str | None = None
    param_list: list[float | int] = Field(default_factory=list)

class RelicSetDetail(NanokaModel):
    """A relic-set document containing keyed pieces and required-piece effect definitions.

    piece_list fills omitted piece IDs from numeric mapping keys; effects exposes
    parsed bonuses ordered by piece count.
    """
    id: int | None = None
    name: str | None = None
    icon: str | None = None
    parts: dict[str, RelicPart] = Field(default_factory=dict)
    require_num: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @computed_field
    @property
    def effects(self) -> list[RelicSetEffectDetail]:
        """Return parsed set effects ordered by their required piece count."""
        result: list[RelicSetEffectDetail] = []
        for key in sorted(
            self.require_num, key=lambda value: int(value) if str(value).isdigit() else 999
        ):
            data = self.require_num[key]
            result.append(
                RelicSetEffectDetail(
                    pieces=int(key) if str(key).isdigit() else 0,
                    desc=data.get("desc"),
                    param_list=data.get("param_list") or data.get("ParamList") or [],
                )
            )
        return result

    @computed_field
    @property
    def piece_list(self) -> list[RelicPart]:
        """Return relic parts, filling missing IDs from numeric provider mapping keys."""
        result: list[RelicPart] = []
        for key, part in self.parts.items():
            if part.id is None and str(key).isdigit():
                part = part.model_copy(update={"id": int(key)})
            result.append(part)
        return result

__all__ = ['RelicSetEffect', 'RelicSetSummary', 'RelicPart', 'RelicSetEffectDetail', 'RelicSetDetail']
