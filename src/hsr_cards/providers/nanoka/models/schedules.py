"""Published endgame schedules and UTC live/test date accessors."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import Field, computed_field
from ..locales import DEFAULT_LOCALE, Locale

from .common import NanokaModel, as_utc, localized_field, parse_datetime

class MazeSchedule(NanokaModel):
    """An endgame catalog season with multilingual names and separate live/test windows.

    Numeric id is required; optional mode/version describe provider context.
    UTC date accessors prefer live boundaries and expose test/deployment dates
    separately. Missing dates stay unknown instead of inventing a live interval.
    """
    id: int
    name: str | None = None
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    begin: str | None = None
    end: str | None = None
    live_begin: str | None = None
    live_end: str | None = None
    param: list[float | int] = Field(default_factory=list)
    mode: str | None = None
    version: str | None = None

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        """Return the requested locale name with optional en/zh/ja/ko fallback.

        Locale aliases are accepted. Return None if absent; invalid aliases raise
        ValueError. Game ruby markup is removed without performing IO.
        """
        if self.name:
            return self.name
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @computed_field
    @property
    def localized_name(self) -> str | None:
        """Return the default-locale schedule name with other-language fallback."""
        return self.display_name()

    @computed_field
    @property
    def live_begins_at(self) -> datetime | None:
        """Return the authoritative live start as UTC, or None if absent/invalid."""
        return parse_datetime(self.live_begin)

    @computed_field
    @property
    def live_ends_at(self) -> datetime | None:
        """Return the authoritative live end as UTC, or None if absent/invalid."""
        return parse_datetime(self.live_end)

    @computed_field
    @property
    def begins_at(self) -> datetime | None:
        """Return the UTC live start, falling back to the test/deployment start."""
        return self.live_begins_at or parse_datetime(self.begin)

    @computed_field
    @property
    def ends_at(self) -> datetime | None:
        """Return the UTC live end, falling back to the test/deployment end."""
        return self.live_ends_at or parse_datetime(self.end)

    @computed_field
    @property
    def has_live_window(self) -> bool:
        """Return whether both authoritative live date fields are published."""
        return bool(self.live_begin and self.live_end)

    @computed_field
    @property
    def test_begins_at(self) -> datetime | None:
        """Return the test/deployment start as UTC, or None if absent/invalid."""
        return parse_datetime(self.begin)

    @computed_field
    @property
    def test_ends_at(self) -> datetime | None:
        """Return the test/deployment end as UTC, or None if absent/invalid."""
        return parse_datetime(self.end)

    @computed_field
    @property
    def is_live(self) -> bool:
        """Return whether the current UTC time lies within the effective start/end window."""
        return self.is_live_at()

    @computed_field
    @property
    def is_upcoming(self) -> bool:
        """Return whether the effective start lies after the current UTC time."""
        return bool(self.begins_at and self.begins_at > as_utc())

    @computed_field
    @property
    def has_schedule(self) -> bool:
        """Return whether at least one effective start/end boundary is available."""
        return self.begins_at is not None or self.ends_at is not None

    def is_live_at(self, when: datetime | None = None) -> bool:
        """Return whether a supplied moment lies inclusively within the effective window.

        Omit when to use current UTC time; naive datetimes are interpreted as UTC.
        Return False without both date boundaries. This performs no IO.
        """
        moment = as_utc(when)
        starts, ends = self.begins_at, self.ends_at
        return bool(starts and ends and starts <= moment <= ends)

    @classmethod
    def from_entry(
        cls,
        identifier: str | int,
        payload: dict[str, Any],
        *,
        mode: str | None = None,
        version: str | None = None,
    ) -> "MazeSchedule":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Optional mode/version metadata is merged with payload fields. Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate(
            {"id": int(identifier), "mode": mode, "version": version, **payload}
        )

class PeakSchedule(MazeSchedule):
    """Anomaly Arbitration seasons are ordered but have no date window."""

__all__ = ['MazeSchedule', 'PeakSchedule']
