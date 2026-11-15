"""Measure and draw complete season options and boss mechanics."""
from __future__ import annotations
from typing import Sequence
from ....services.endgame.modes import EffectInfo
from ...common.text import wrap_text
from .drawing import _measure_draw
from .styles import *


def _effect_height(effects: Sequence[EffectInfo], width: int) -> int:
    draw = _measure_draw()
    return sum(
        14 + len(wrap_text(draw, effect.name, width, font(18, "bold"))) * 24
        + len(wrap_text(draw, effect.text, width, font(17))) * 23
        for effect in effects
    )


def _draw_effects(draw, x: int, y: int, width: int, effects: Sequence[EffectInfo]) -> int:
    start = y
    for effect in effects:
        y += 8
        for line in wrap_text(draw, effect.name, width, font(18, "bold")):
            draw.text((x, y), line, font=font(18, "bold"), fill=GOLD, anchor="lt")
            y += 24
        for line in wrap_text(draw, effect.text, width, font(17)):
            draw.text((x, y), line, font=font(17), fill=BODY, anchor="lt")
            y += 23
        y += 6
    return y - start
