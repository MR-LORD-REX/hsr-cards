"""Domain wrappers that retain both Nanoka summaries and detail models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


from .constants import MODE_LABELS
from .locales import DEFAULT_LOCALE, Locale
from .models import EndgameDetail, MazeSchedule, PeakDetail, StageEvent, StageLevel


class _ResultWrapper:
    """Retain a catalog summary, optional detail model, and display locale.

    Attribute lookup checks the summary first and only falls back to detail when
    the attribute is missing. Wrapping models performs no network or file IO.
    """
    summary: Any
    detail: Any

    def __init__(self, summary: Any, detail: Any | None = None, locale: Locale | str = DEFAULT_LOCALE):
        """Wrap already resolved models with an optional detail and display locale.

        locale accepts supported Locale aliases and defaults to English; unsupported
        aliases raise ValueError. The supplied models are retained without copying,
        network requests, or file access.
        """
        self.summary = summary
        self.detail = detail
        self.locale = Locale.normalize(locale)

    def __getattr__(self, name: str):
        if name in {"summary", "detail", "locale"}:
            raise AttributeError(name)
        try:
            return getattr(self.summary, name)
        except AttributeError:
            detail = object.__getattribute__(self, "detail")
            if detail is None:
                raise
            return getattr(detail, name)

    def display_name(self, locale: Locale | str | None = None, *, fallback: bool = True) -> str | None:
        """Return the summary name for locale or this wrapper locale.

        fallback=True permits other-language text. Return None when no text exists;
        invalid locale aliases raise ValueError and the operation performs no IO.
        """
        return self.summary.display_name(locale or self.locale, fallback=fallback)

    def __repr__(self) -> str:
        identifier = getattr(self.summary, "id", "?")
        return f"{type(self).__name__}(id={identifier}, name={self.display_name()!r})"

class Character(_ResultWrapper):
    """A resolved character summary with an optional character detail model.

    Expose summary fields first, then missing detail fields, and retain the query
    locale for display_name(). Constructing the wrapper performs no IO.
    """
    pass

class LightCone(_ResultWrapper):
    """A resolved light-cone summary with optional refinements and stat details.

    Expose summary fields first, then missing detail fields, and retain the query
    locale for display_name(). Constructing the wrapper performs no IO.
    """
    pass

class RelicSet(_ResultWrapper):
    """A resolved relic-set summary with optional piece and effect details.

    Expose summary fields first, then missing detail fields, and retain the query
    locale for display_name(). Constructing the wrapper performs no IO.
    """
    pass

class Monster(_ResultWrapper):
    """A resolved monster summary with optional base stats and variant details.

    Expose summary fields first, then missing detail fields, and retain the query
    locale for display_name(). Constructing the wrapper performs no IO.
    """
    pass

@dataclass
class BossEncounter:
    """Resolved endgame boss data for one stage (card-generator friendly)."""

    mode: str
    season: MazeSchedule
    stage: StageLevel | None = None
    detail: EndgameDetail | PeakDetail | None = None
    bosses: list[Monster] = field(default_factory=list)
    waves: list[StageEvent] = field(default_factory=list)
    monster_ids: list[int] = field(default_factory=list)
    locale: Locale = DEFAULT_LOCALE

    @property
    def mode_label(self) -> str:
        """Return the display label for the canonical mode."""
        return MODE_LABELS[self.mode]

    @property
    def id(self) -> int:
        """Return the published season/schedule ID."""
        return self.season.id

    @property
    def name(self) -> str | None:
        """Return the schedule display name, or None when no localized name is present."""
        return self.season.display_name()

    @property
    def version(self) -> str | None:
        """Return the published schedule build version, or None when unknown."""
        return self.season.version

    @property
    def boss(self) -> "Monster | None":
        """Return the first resolved boss, or None when no bosses were resolved."""
        return self.bosses[0] if self.bosses else None

    def boss_names_for(
        self, locale: Locale | str | None = None, *, fallback: bool = True
    ) -> list[str]:
        """Return localized boss names, falling back to IDs when names are missing.

        Locale defaults to the encounter locale; fallback=True accepts other-language
        text. Invalid locale aliases raise ValueError; this performs no IO.
        """
        loc = locale or self.locale
        return [
            boss.display_name(loc, fallback=fallback) or str(boss.id)
            for boss in self.bosses
        ]

    @property
    def boss_names(self) -> list[str]:
        """Return boss names in the encounter locale, falling back to numeric IDs."""
        return self.boss_names_for()

    @property
    def stage_name(self) -> str | None:
        """Return the resolved stage name, or None if the stage is absent."""
        return self.stage.name if self.stage else None

    @property
    def starts_at(self) -> datetime | None:
        """Return the detail UTC start, falling back to the effective schedule start."""
        if isinstance(self.detail, EndgameDetail):
            return self.detail.starts_at or self.season.begins_at
        return self.season.begins_at

    @property
    def ends_at(self) -> datetime | None:
        """Return the detail/schedule effective UTC end, or None when no date exists."""
        if isinstance(self.detail, EndgameDetail):
            return self.detail.ends_at or self.season.ends_at
        return self.season.ends_at

    def __repr__(self) -> str:
        names = ", ".join(self.boss_names) or "-"
        return f"BossEncounter(mode={self.mode!r}, season={self.season.id}, bosses=[{names}])"

@dataclass
class EndgameSeason:
    """A mode-specific schedule plus its detail document."""

    mode: str
    schedule: MazeSchedule
    detail: EndgameDetail | PeakDetail | None = None

    @property
    def id(self) -> int:
        """Return the published season/schedule ID."""
        return self.schedule.id

    @property
    def name(self) -> str | None:
        """Return the schedule display name, or None when no localized name is present."""
        return self.schedule.display_name()

    @property
    def begins_at(self) -> datetime | None:
        """Return the schedule live UTC start, falling back to the test start."""
        return self.schedule.begins_at

    @property
    def ends_at(self) -> datetime | None:
        """Return the detail/schedule effective UTC end, or None when no date exists."""
        return self.schedule.ends_at

    @property
    def is_live(self) -> bool:
        """Return schedule live status; undated schedules retain the existing True fallback."""
        return self.schedule.is_live if self.schedule.has_schedule else True

    @property
    def boss_ids(self) -> list[int]:
        """Return published detail boss IDs, or [] if detail data is absent."""
        return self.detail.boss_ids if self.detail else []

    @property
    def boss_names(self) -> list[str]:
        """Return the AA peak boss name, or [] for other modes or absent peak data."""
        if isinstance(self.detail, PeakDetail):
            return [self.detail.boss_name] if self.detail.boss_name else []
        return []

    def __repr__(self) -> str:
        return f"EndgameSeason(mode={self.mode!r}, id={self.id}, name={self.name!r})"

__all__ = ['Character', 'LightCone', 'RelicSet', 'Monster', 'BossEncounter', 'EndgameSeason']
