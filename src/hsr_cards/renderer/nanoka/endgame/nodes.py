"""Measured enemy-wave panels and their mode-specific effects."""
from __future__ import annotations
from typing import Any
from ....core.text import format_hp
from ....services.endgame.models import MonsterInfo, NodeInfo
from ...common.images import paste_icon
from ...common.text import wrap_text
from .drawing import _measure_draw, rounded
from .effects import _effect_height, _draw_effects
from .styles import *


def _monster_lines(monster: MonsterInfo, width: int) -> list[tuple[str, Any, int]]:
    draw = _measure_draw()
    name = monster.name + (f"  x{monster.count}" if monster.count > 1 else "")
    lines = [(line, TEXT, 19) for line in wrap_text(draw, name, width, font(19, "bold"))]
    lines.extend((line, GOLD, 17) for line in wrap_text(draw, monster.hp_text, width, font(17, "bold")))
    if monster.corrosion_hp is not None and monster.corrosion_ratio:
        text = f"Voracity HP +{format_hp(monster.corrosion_hp)} ({monster.corrosion_ratio:.0%})"
        lines.extend((line, RED, 16) for line in wrap_text(draw, text, width, font(16, "bold")))
    return lines


def monster_row_height(monster: MonsterInfo, name_width: int) -> int:
    """Measure an enemy row in pixels, including wrapped name/HP/count text and weakness glyphs."""
    return max(80, sum(size + 5 for _, _, size in _monster_lines(monster, name_width)) + (28 if monster.weaknesses else 0) + 16)


def _node_monster_height(node: NodeInfo, width: int) -> int:
    height = sum(28 + sum(monster_row_height(monster, width - 106) for monster in wave) for wave in node.waves)
    if node.corrosion_targets:
        draw = _measure_draw()
        height += 34
        for target in node.corrosion_targets:
            height += 30 + 23 * len(wrap_text(draw, target.name, width - 40, font(17, "bold")))
    return height


def node_panel_height(node: NodeInfo, width: int) -> int:
    """Measure all node waves/corrosion/effects with the same pixel widths and column split used in drawing."""
    split = width > 700 and bool(node.season_effects or node.stage_effects)
    monster_width = 410 if split else width
    effects_width = width - 450 if split else width - 36
    effects_height = sum(32 + _effect_height(effects, effects_width) for effects in (node.season_effects, node.stage_effects) if effects)
    enemies_height = _node_monster_height(node, monster_width)
    content = max(enemies_height, effects_height) if split else enemies_height + effects_height
    elements_height = 30 if node.elements else 0
    return 66 + elements_height + content + (46 if node.invasion_level else 0) + 12


def draw_node_panel(canvas, draw, x: int, y: int, width: int, node: NodeInfo, icons) -> int:
    """Draw a resolved node into canvas at x/y and return its pixel height, preserving all waves and mode effects."""
    height = node_panel_height(node, width)
    rounded(draw, (x, y, x + width, y + height), 18, PANEL, EDGE)
    draw.text((x + 18, y + 20), node.label or f"NODE {node.number}", font=font(20, "bold"), fill=GOLD, anchor="lm")
    if node.level:
        draw.text((x + width - 18, y + 20), f"Lv. {node.level}", font=font(17, "bold"), fill=MUTED, anchor="rm")
    cursor = y + 46
    if node.elements:
        draw.text((x + 18, cursor), "RECOMMENDED", font=font(12, "bold"), fill=MUTED, anchor="lt")
        for index, element in enumerate(node.elements):
            draw.text((x + 144 + 30 * index, cursor - 3), ICON_GLYPHS.get(element, "b"), font=icon_font(23), fill=ELEMENT_COLORS.get(element, MUTED), anchor="lt")
        cursor += 30
    content_top = cursor
    split = width > 700 and bool(node.season_effects or node.stage_effects)
    monster_width = 410 if split else width
    for wave_index, wave in enumerate(node.waves, start=1):
        draw.text((x + 18, cursor), f"WAVE {wave_index}", font=font(14, "bold"), fill=MUTED, anchor="lt")
        cursor += 28
        for monster in wave:
            paste_icon(canvas, monster.icon, (x + 18, cursor, x + 80, cursor + 72))
            line_y = cursor + 5
            for text, color, size in _monster_lines(monster, monster_width - 106):
                draw.text((x + 90, line_y), text, font=font(size, "bold"), fill=color, anchor="lt")
                line_y += size + 5
            for index, weakness in enumerate(monster.weaknesses):
                draw.text((x + 90 + 29 * index, line_y), ICON_GLYPHS.get(weakness, "b"), font=icon_font(22), fill=ELEMENT_COLORS.get(weakness, MUTED), anchor="lt")
            cursor += monster_row_height(monster, monster_width - 106)
    if node.corrosion_targets:
        draw.text((x + 18, cursor + 8), "ADDITIONAL CORROSION TARGETS", font=font(14, "bold"), fill=RED, anchor="lt")
        cursor += 34
        for target in node.corrosion_targets:
            for line in wrap_text(draw, target.name, monster_width - 40, font(17, "bold")):
                draw.text((x + 20, cursor), line, font=font(17, "bold"), fill=BODY, anchor="lt")
                cursor += 23
            draw.text((x + 20, cursor), f"Voracity HP +{format_hp(target.bonus_hp)} ({target.bonus_ratio:.0%})", font=font(16, "bold"), fill=RED, anchor="lt")
            cursor += 30
    effects_x = x + 430 if split else x + 18
    effects_y = content_top if split else cursor
    effects_width = width - 450 if split else width - 36
    for title, effects in (("SEASON EFFECTS", node.season_effects), ("STAGE EFFECTS", node.stage_effects)):
        if effects:
            draw.text((effects_x, effects_y + 7), title, font=font(14, "bold"), fill=CYAN, anchor="lt")
            effects_y += 32
            effects_y += _draw_effects(draw, effects_x, effects_y, effects_width, effects)
    if node.invasion_level:
        rounded(draw, (x + 14, y + height - 46, x + width - 14, y + height - 12), 12, (53, 27, 38, 255), (132, 59, 67, 255))
        ratio = f"  /  +{node.corrosion_ratio:.0%} HP" if node.corrosion_ratio else ""
        draw.text((x + 26, y + height - 29), f"VORACITY CORROSION Lv. {node.invasion_level}{ratio}", font=font(15, "bold"), fill=RED, anchor="lm")
    return height
