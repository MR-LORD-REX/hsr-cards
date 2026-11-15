"""Compose synchronous skills sheets and optional summary/page variants."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
import math
from hsr_cards.renderer.nanoka.skills.cards import eidolon_card, measure_eidolon_card, measure_skill_card, skill_card
from hsr_cards.renderer.nanoka.skills.header import draw_footer, header, page_background, section_title, ui
from hsr_cards.renderer.nanoka.skills.layout import distribute_even, plan_page
from hsr_cards.renderer.nanoka.skills.models import SkillData, SkillGroup, SkillPanel, SkillsCardResult
from hsr_cards.renderer.nanoka.skills.styles import BOTTOM_RESERVE, CONTENT_TOP, EID_GAP, GAP, HEADER_H, LEFT_W, M, RIGHT_W, RIGHT_X, ROW_GAP, SECTION_GAP, SECTION_HEAD_H, SECTION_TOP, W
from hsr_cards.renderer.nanoka.skills.tables import build_sections, build_tables


def render_full(data: SkillData) -> SkillsCardResult:
    """Draw the complete skill/eidolon sheet and build its rich-message payloads.

    Accept resolved SkillData and return SkillsCardResult with a 1920-pixel-wide RGBA
    image, parameter tables, dropdown indices and sections. Height grows with kit
    content, retaining grouped continuation parts and comparison highlights. Reads
    cached art/fonts only; performs no provider requests or generated-image writes.
    Font/image/layout errors propagate and no client lifecycle is owned here.
    """
    scratch = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(scratch)
    plan = plan_page(data, draw)
    height = plan["height"]
    body_size = plan["body"]
    eid_size = plan["eid"]
    available = height - CONTENT_TOP - BOTTOM_RESERVE

    eid_heights, eid_gap = distribute_even(plan["eid_heights"], EID_GAP, available)

    canvas = page_background(W, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, W, HEADER_H)
    section_title(draw, RIGHT_X, SECTION_TOP, ui(data, "eidolons"), ui(data, "eidolons_sub"), RIGHT_W, data.locale)

    y = CONTENT_TOP
    for (title, groups, subtitle), layout in zip(plan["sections"], plan["layouts"]):
        section_title(draw, M, y, title, subtitle, LEFT_W, data.locale)
        y += SECTION_HEAD_H
        cols = [0.0] * layout["cols"]
        for indices, group_h in zip(layout["groups"], layout["group_heights"]):
            slot = cols.index(min(cols))
            x = M + slot * (layout["width"] + GAP)
            panel_y = y + cols[slot]
            for index in indices:
                panel = layout["panels"][index]
                panel_h = layout["heights"][index]
                skill_card(canvas, draw, data, panel, x, round(panel_y), layout["width"], panel_h, body_size)
                panel_y += panel_h + ROW_GAP
            cols[slot] += group_h + ROW_GAP
        y += max(cols) + SECTION_GAP

    y = CONTENT_TOP
    for rank, eid_h in zip(data.eidolons, eid_heights):
        eidolon_card(canvas, draw, data, rank, RIGHT_X, y, RIGHT_W, eid_h, eid_size)
        y += eid_h + eid_gap

    draw_footer(draw, W, height, data, ui(data, "footer"))
    tables, dropdowns = build_tables(data)
    return SkillsCardResult(
        image=canvas,
        tables=tables,
        dropdowns=dropdowns,
        sections=build_sections(data),
    )


def render_summary(data: SkillData) -> Image.Image:
    """Draw up to six skills and six eidolons as a compact 1920-pixel-wide RGBA image using resolved data and cached assets."""
    width = W
    col_w = (LEFT_W - GAP) // 2
    body_size = 15
    eid_body = 14
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    skills = data.skills[:6]
    panels = [SkillPanel(group=group, desc=group.raw_desc or group.desc, extras=False, stats=False) for group in skills]
    row_need = []
    for index in range(0, len(panels), 2):
        heights = [
            measure_skill_card(probe, data, panel, col_w, body_size)
            for panel in panels[index:index + 2]
        ]
        row_need.append(max(heights, default=160))
    eid_need = [measure_eidolon_card(probe, data, rank, RIGHT_W, eid_body, extras=False) for rank in data.eidolons]
    left_h = sum(row_need) + ROW_GAP * max(0, len(row_need) - 1)
    right_h = sum(eid_need) + EID_GAP * max(0, len(eid_need) - 1)
    height = max(1080, CONTENT_TOP + max(left_h, right_h) + BOTTOM_RESERVE)
    canvas = page_background(width, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, width, HEADER_H)
    section_title(draw, M, SECTION_TOP, ui(data, "skills"), ui(data, "skills_sub"), LEFT_W, data.locale)
    section_title(draw, RIGHT_X, SECTION_TOP, ui(data, "eidolons"), ui(data, "eidolons_sub"), RIGHT_W, data.locale)
    y = CONTENT_TOP
    for row, row_h in enumerate(row_need):
        for col in range(2):
            index = row * 2 + col
            if index >= len(panels):
                continue
            x = M + col * (col_w + GAP)
            skill_card(canvas, draw, data, panels[index], x, y, col_w, row_h, body_size=body_size)
        y += row_h + ROW_GAP
    y = CONTENT_TOP
    for rank, eid_h in zip(data.eidolons, eid_need):
        eidolon_card(canvas, draw, data, rank, RIGHT_X, y, RIGHT_W, eid_h, body_size=eid_body, extras=False)
        y += eid_h + EID_GAP
    draw_footer(draw, width, height, data, ui(data, "footer"))
    return canvas


def render_skill_page(data: SkillData, skills: list[SkillGroup], page_number: int, page_count: int) -> Image.Image:
    """Draw supplied resolved skills on a 1920-pixel-wide RGBA page with measured height; page metadata is caller-supplied."""
    width = 1920
    col_w = (W - M * 2 - GAP) // 2
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    panels = [
        SkillPanel(group=group, desc=group.raw_desc or group.desc, extras=True, stats=True)
        for group in skills
    ]
    heights = [measure_skill_card(probe, data, panel, col_w, 16) for panel in panels]
    row_heights = [max(heights[i:i + 2]) for i in range(0, len(heights), 2)]
    height = max(1440, CONTENT_TOP + sum(row_heights) + ROW_GAP * max(0, len(row_heights) - 1) + BOTTOM_RESERVE + 10)
    canvas = page_background(width, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, width, HEADER_H)
    section_title(draw, M, SECTION_TOP, ui(data, "skills"), f"{page_number} / {page_count}", W - M * 2, data.locale)
    y = CONTENT_TOP
    for row, row_h in enumerate(row_heights):
        for col in range(2):
            index = row * 2 + col
            if index >= len(panels):
                continue
            x = M + col * (col_w + GAP)
            skill_card(canvas, draw, data, panels[index], x, y, col_w, row_h, body_size=16)
        y += row_h + ROW_GAP
    draw_footer(draw, width, height, data, ui(data, "footer"))
    return canvas


def render_eidolon_page(data: SkillData) -> Image.Image:
    """Draw up to six resolved eidolons in two columns on a 1920-pixel-wide RGBA page whose height grows with text."""
    width = 1920
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    col_w = (width - M * 2 - GAP) // 2
    need = [measure_eidolon_card(probe, data, rank, col_w, 15) for rank in data.eidolons[:6]]
    row_need = [max(need[i:i + 2]) for i in range(0, len(need), 2)]
    height = max(1080, CONTENT_TOP + sum(row_need) + 12 * max(0, len(row_need) - 1) + BOTTOM_RESERVE)
    canvas = page_background(width, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, width, HEADER_H)
    section_title(draw, M, SECTION_TOP, ui(data, "eidolons"), "E1 - E6", W - M * 2, data.locale)
    card_h = 220
    col_w = (W - M * 2 - GAP) // 2
    ranks = data.eidolons[:6]
    rows = max(1, math.ceil(len(ranks) / 2))
    row_space = (height - CONTENT_TOP - BOTTOM_RESERVE - 12 * max(0, rows - 1)) // rows
    heights = [measure_eidolon_card(draw, data, rank, col_w, 15) for rank in ranks]
    row_heights = [max(heights[i:i + 2]) for i in range(0, len(heights), 2)]
    y = CONTENT_TOP
    for row, row_h in enumerate(row_heights):
        for col in range(2):
            index = row * 2 + col
            if index >= len(ranks):
                continue
            x = M + col * (col_w + GAP)
            eidolon_card(canvas, draw, data, ranks[index], x, y, col_w, row_h, body_size=15)
        y += row_h + 12
    draw_footer(draw, width, height, data, ui(data, "footer"))
    return canvas
