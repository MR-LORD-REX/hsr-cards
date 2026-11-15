"""Mode validation, floor defaults, and authoritative live-window labels."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Sequence
from ...core.types import GameMode
from ...nanoka.models import MazeSchedule
MODE_NAMES = {"MOC": "MEMORY OF CHAOS", "PF": "PURE FICTION", "AS": "APOCALYPTIC SHADOW", "AA": "ANOMALY ARBITRATION"}
MODE_CANONICAL = {"MOC": "maze", "PF": "maze_extra", "AS": "maze_boss", "AA": "maze_peak"}
DEFAULT_FLOORS = {"MOC": (11, 12), "PF": (3, 4), "AS": (3, 4)}


def mode_label(mode: GameMode) -> str:
    """Return the uppercase display title for a canonical MOC/PF/AS/AA code; unknown keys raise KeyError."""
    return MODE_NAMES[mode]


def canonical_mode(mode: GameMode | str) -> str:
    """Map a trimmed, case-insensitive MOC/PF/AS/AA code to its Nanoka mode; unsupported values raise ValueError."""
    key = str(mode).strip().upper()
    if key not in MODE_CANONICAL:
        raise ValueError("game_mode must be one of MOC, PF, AS, or AA")
    return MODE_CANONICAL[key]


def normalize_floors(game_mode: GameMode | str, floors: Sequence[int] | int | None) -> list[int]:
    """Return sorted, deduplicated integer floor requests for a recognized mode.

    None selects MOC 11/12 or PF/AS 3/4; deferred AA has no default floors. Numeric
    conversion and unsupported-mode errors propagate. This normalization does not
    check whether a floor exists in a particular season.
    """
    key = str(game_mode).strip().upper()
    if key not in DEFAULT_FLOORS and key != "AA":
        raise ValueError("game_mode must be one of MOC, PF, AS, or AA")
    if key == "AA":
        return [] if floors is None else sorted({int(floor) for floor in floors})
    if floors is None:
        return list(DEFAULT_FLOORS[key])
    values = [floors] if isinstance(floors, int) else list(floors)
    return sorted({int(floor) for floor in values})


def season_status(schedule: MazeSchedule, now: datetime | None = None) -> str:
    """Classify an authoritative live window at now, defaulting to current UTC.

    Return UNSCHEDULED for absent live windows, UPCOMING before the start, ENDED
    strictly after the end, otherwise LIVE. Deployment/beta dates are never used to
    infer live status; supplied datetimes must be mutually timezone-compatible.
    """
    moment = now or datetime.now(timezone.utc)
    if not schedule.has_live_window:
        return "UNSCHEDULED"
    start, end = schedule.live_begins_at, schedule.live_ends_at
    if start and start > moment:
        return "UPCOMING"
    if end and end < moment:
        return "ENDED"
    return "LIVE"


def format_date(value: datetime | None) -> str:
    """Format a supplied datetime as DD Mon YYYY without timezone conversion; None displays a dash."""
    return value.strftime("%d %b %Y") if value else "-"
