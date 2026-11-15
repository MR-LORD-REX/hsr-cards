"""Pure monster HP calculations for variants, phases, and corrosion."""
from __future__ import annotations
from typing import Any, Sequence
from ...nanoka.models import MonsterDetail, StageEvent
from .models import HpBar


def find_ratio(rows: Sequence[dict[str, Any]], key: str, value: int | None) -> float:
    """Return a matching row HPRatio, defaulting to 1.0 for absent IDs/rows/zero ratios; numeric errors propagate."""
    if value is None:
        return 1.0
    for row in rows:
        if int(row.get(key, -1)) == int(value):
            return float(row.get("HPRatio", 1) or 1)
    return 1.0


def raw_monster_phases(detail: MonsterDetail | None) -> list[dict[str, Any]]:
    """Return mapping phase entries from detail/extra payloads, or [] when phases/details are absent."""
    if detail is None:
        return []
    payload = getattr(detail, "__pydantic_extra__", None) or {}
    phases = getattr(detail, "phase_list", None) or payload.get("phase_list")
    if isinstance(phases, list):
        return [phase for phase in phases if isinstance(phase, dict)]
    return []


def monster_hp_values(
    event: StageEvent,
    identifier: int,
    detail: MonsterDetail | None,
    hard_rows: Sequence[dict[str, Any]],
    elite_rows: Sequence[dict[str, Any]],
    values: dict[str, Any],
) -> list[HpBar]:
    """Calculate one HP bar per monster phase from already resolved provider data.

    Multiply base HP by hard-level, elite and stage-variant ratios, then each phase's
    maximum-HP ratio. Return HpBar entries, or [] when base HP is unavailable; a
    monster with no phases has one bar. Missing multipliers default to one and
    numeric conversion errors propagate. No IO or input mutation occurs.
    """
    stats = values.get(str(identifier)) or {}
    base = float((detail.hp_base if detail is not None else None) or stats.get("HPBase") or 0)
    if not base:
        return []
    variant_ratio = 1.0
    level = event.level
    if detail is not None:
        variant = next((entry for entry in detail.child if str(entry.id) == str(identifier)), None)
        if variant is None and detail.child:
            variant = detail.child[0]
        if variant is not None:
            variant_ratio = float(variant.hp_modify_ratio or 1)
    hard_ratio = 1.0
    for row in hard_rows:
        if int(row.get("HardLevelGroup", -1)) == int(event.hard_level_group or -1) and int(row.get("Level", -1)) == int(level or -1):
            hard_ratio = float(row.get("HPRatio", 1) or 1)
            break
    elite_ratio = find_ratio(elite_rows, "EliteGroup", event.elite_group)
    per_bar = base * hard_ratio * elite_ratio * variant_ratio
    phases = raw_monster_phases(detail)
    if not phases:
        return [HpBar(per_bar, None)]
    bars: list[HpBar] = []
    for index, phase in enumerate(phases, start=1):
        ratio = float(phase.get("phase_max_hp_ratio", 1) or 1)
        bars.append(HpBar(per_bar * ratio, int(phase.get("phase_num") or index)))
    return bars


def invasion_ratio(event: StageEvent) -> float | None:
    """Return the corrosion HP ratio from the invasion buff second parameter, or None when unavailable."""
    if event.invasion is None:
        return None
    params = getattr(event.invasion, "maze_buff_param", None) or []
    return float(params[1]) if len(params) > 1 else None
