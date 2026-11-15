"""Mode-specific Nanoka wave and effect adapters for endgame floor cards."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from ...nanoka.models import StageEvent, StageLevel

ExpandText = Callable[[str | None, Sequence[float | int]], str]


@dataclass
class EffectInfo:
    """An expanded season option or boss mechanic ready to draw."""

    name: str
    text: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any], expand: ExpandText) -> "EffectInfo":
        """Expand display parameters; percentage placeholders use ratios."""
        return cls(
            name=expand(payload.get("name"), []),
            text=expand(payload.get("desc"), payload.get("param") or []),
        )


def node_wave_specs(
    stage: StageLevel, number: int, event: StageEvent, mode: str,
) -> list[tuple[StageEvent, dict[int, int], float]]:
    """Return each wave's scaling, counts, and HP multiplier.

    PF's infinite lists contain the full spawn roster, including enemies absent
    from the initial monster slots. Its second ability parameter adds HP on top
    of the wave's elite-group scaling.
    """
    suffix = str(number) if number in (1, 2) else ""
    infinite = getattr(stage, f"infinite_list{suffix}") if mode == "PF" else {}
    if infinite:
        return [
            (
                event.model_copy(update={"elite_group": wave.elite_group}),
                dict(Counter(wave.monster_group_id_list)),
                1 + (float(wave.param_list[1]) if len(wave.param_list) > 1 else 0),
            )
            for wave in infinite.values()
        ]
    return [(event, dict(Counter(slot.monster_ids)), 1.0) for slot in event.monster_list]


def node_effects(
    stage: StageLevel, number: int, payload: dict[str, Any], expand: ExpandText,
) -> tuple[list[EffectInfo], list[EffectInfo]]:
    """Resolve AS season options and boss mechanics for the matching node."""
    season = [EffectInfo.from_payload(item, expand) for item in payload.get(f"buff_list{number}", [])]
    suffix = str(number) if number in (1, 2) else ""
    config = getattr(stage, f"boss_monster_config{suffix}")
    mechanics = [EffectInfo.from_payload(item.model_dump(), expand) for item in config.tag_list] if config else []
    return season, mechanics
