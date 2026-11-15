"""Pure endgame floor composition; no provider or cache access."""
from __future__ import annotations
from typing import Sequence
from PIL import Image, ImageDraw
from ....services.endgame.models import FloorCardData
from ....services.endgame.modes import EffectInfo
from ....services.endgame.schedules import format_date, mode_label
from ...common.text import wrap_text
from .drawing import _measure_draw, rounded, draw_chip
from .effects import _effect_height, _draw_effects
from .nodes import draw_node_panel, node_panel_height
from .styles import *


def render_floor_card(data: FloorCardData) -> Image.Image:
    """Draw one fully resolved floor as a 1080-pixel-wide RGBA PIL image.

    Measure and assemble all node waves, HP/corrosion text, buffs and conditions;
    height grows with content. data must already contain provider data/artwork and
    status/date labels. No HTTP, schedule selection or image-cache writes occur.
    Font/image/layout errors propagate; no provider lifecycle is owned here.
    """
    inner_width = W - 2 * M
    column_width = (inner_width - GAP) // 2
    # Build each block separately so long effects never overlap the next panel.
    blocks: list[Image.Image] = []
    def text_panel(title: str, effects: Sequence[EffectInfo], color=CYAN):
        height = 60 + _effect_height(effects, inner_width - 44)
        panel = Image.new("RGBA", (inner_width, height), BG)
        draw = ImageDraw.Draw(panel)
        rounded(draw, (0, 0, inner_width - 1, height - 1), 18, PANEL, EDGE)
        draw.text((22, 18), title, font=font(15, "bold"), fill=color, anchor="lt")
        _draw_effects(draw, 22, 44, inner_width - 44, effects)
        blocks.append(panel)

    header_draw = _measure_draw()
    title_lines = wrap_text(header_draw, data.season_name or data.stage_name, inner_width, font(36, "bold"))
    stage_lines = wrap_text(header_draw, data.stage_name, inner_width - 180, font(19, "bold"))
    header = Image.new("RGBA", (inner_width, 142 + len(title_lines) * 44 + max(0, len(stage_lines) - 1) * 25), BG)
    draw = ImageDraw.Draw(header)
    draw.text((0, 0), mode_label(data.mode), font=font(21, "bold"), fill=PURPLE, anchor="lt")
    color = LIVE if data.status == "LIVE" else UPCOMING if data.status == "UPCOMING" else ENDED
    badge_width = int(draw.textlength(data.status, font=font(16, "bold"))) + 26
    draw_chip(draw, (inner_width - badge_width, 0), data.status, color=color, size=16)
    y = 48
    for line in title_lines:
        draw.text((0, y), line, font=font(36, "bold"), fill=TEXT, anchor="lt")
        y += 44
    y += 12
    draw.text((0, y), f"FLOOR {data.floor}", font=font(26, "bold"), fill=GOLD, anchor="lt")
    for line in stage_lines:
        draw.text((180, y + 3), line, font=font(19, "bold"), fill=BODY, anchor="lt")
        y += 25
    draw.text((0, y + 22), f"{format_date(data.begins_at)} - {format_date(data.ends_at)}", font=font(16, "bold"), fill=MUTED, anchor="lt")
    blocks.append(header)
    if data.buff_text:
        text_panel("SEASON BUFF", [EffectInfo(data.buff_name, data.buff_text)], GOLD)
    if data.conditions or data.special:
        text_panel("CLEAR CONDITIONS", [EffectInfo("", "\n".join([*data.conditions, *([data.special] if data.special else [])]))])
    if data.season_effects:
        text_panel("SEASON OPTIONS", data.season_effects, PURPLE)
    if data.grit_effects:
        text_panel("GRIT EFFECTS", data.grit_effects, PURPLE)
    if data.mode == "AS":
        groups = [[node] for node in data.nodes]
    else:
        groups = [[node for node in data.nodes if node.number in (1, 2)]]
        groups.extend([node] for node in data.nodes if node.number not in (1, 2))
    for group in groups:
        if not group:
            continue
        width = column_width if len(group) == 2 else inner_width
        height = max(node_panel_height(node, width) for node in group)
        panel = Image.new("RGBA", (inner_width, height), BG)
        draw = ImageDraw.Draw(panel)
        for index, node in enumerate(group):
            draw_node_panel(panel, draw, index * (width + GAP), 0, width, node, data.element_icons)
        blocks.append(panel)
    height = M + sum(block.height for block in blocks) + GAP * len(blocks) + 52
    canvas = Image.new("RGBA", (W, height), BG)
    y = M
    for block in blocks:
        canvas.alpha_composite(block, (M, y))
        y += block.height + GAP
    draw = ImageDraw.Draw(canvas)
    draw.line((M, height - 44, W - M, height - 44), fill=EDGE, width=1)
    draw.text((M, height - 23), "HSR  /  NANOKA", font=font(15, "bold"), fill=MUTED, anchor="lm")
    draw.text((W - M, height - 23), f"{data.mode}  /  {data.season.id}  /  F{data.floor}", font=font(15, "bold"), fill=MUTED, anchor="rm")
    return canvas
