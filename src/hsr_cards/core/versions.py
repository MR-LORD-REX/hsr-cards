"""Parse single/comparison build selections without requesting provider data."""
from __future__ import annotations
from collections.abc import Sequence
from datetime import datetime


def parse_versions(
    version: str | Sequence[str] | None,
) -> tuple[str | None, str | None]:
    """Normalize a build selection to (from_version, to_version) without provider IO.

    None/empty selections return (None, None), signaling newest-build discovery to
    callers. A string or one nonempty sequence item selects one build; two items
    preserve the supplied older/newer order. More than two items raises ValueError;
    this function does not check publication or sort build labels.
    """
    if version is None:
        return None, None
    if isinstance(version, str):
        return version, None
    values = [str(item) for item in version if item]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], None
    if len(values) > 2:
        raise ValueError("At most two versions can be compared (from, to).")
    return values[0], values[1]


def version_label(
    version: str | None,
    compare_from: str | None = None,
    compare_to: str | None = None,
) -> str:
    """Return an older-to-newer comparison label when both are supplied, otherwise the single/fallback build label."""
    if compare_from and compare_to:
        return f"{compare_from} \u2192 {compare_to}"
    return version or compare_to or ""


def version_datetime(version: str) -> datetime | None:
    """Interpret numeric build components as a datetime for deterministic ordering.

    The first numeric component is the year, the second the month (default one),
    and the day is one. This is not a publication/live timestamp. No numeric
    components returns None; out-of-range datetime components raise ValueError.
    """
    try:
        parts = [int(part) for part in version.split(".") if part.isdigit()]
    except ValueError:
        return None
    if not parts:
        return None
    return datetime(parts[0], parts[1] if len(parts) > 1 else 1, 1)
