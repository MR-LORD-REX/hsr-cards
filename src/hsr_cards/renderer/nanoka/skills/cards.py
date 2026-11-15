"""Measure and draw individual skill, glossary, and eidolon cards."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import GOLD
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import PURPLE
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import composite_panel
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.skills.assets import eidolon_icon, previous_eidolon_icon, skill_icon
from hsr_cards.renderer.nanoka.skills.decorations import change_badge, change_overlay
from hsr_cards.renderer.nanoka.skills.header import fit, ui, wrap_locale
from hsr_cards.renderer.nanoka.skills.models import GlossaryTerm, RankRow, SkillData, SkillGroup, SkillPanel
from hsr_cards.renderer.nanoka.skills.preparation import value_color
from hsr_cards.renderer.nanoka.skills.styles import CARD_EDGE, CARD_FILL, DASH, EID_BOTTOM, EID_PAD, EID_TITLE_SIZE, GLOSSARY_BODY_SIZE, GLOSSARY_GAP, GLOSSARY_INNER, GLOSSARY_LINE, GLOSSARY_TITLE_SIZE, SKILL_BOTTOM, SKILL_PAD, SKILL_TITLE_SIZE, SKILL_TITLE_STEP, STATS_GAP, STATS_H, STATS_ROW, VALUE, WEIGHT_REGULAR, WEIGHT_SEMI
from hsr_cards.renderer.nanoka.skills.text import description_tokens, draw_lines, eidolon_tokens, glossary_tokens, layout_lines, measure_runs, trim_blank_lines
from hsr_cards.renderer.nanoka.skills.typography import font_w, title_runs


def skill_text_width(width: int) -> int:
    """Return usable description width after both skill-card pixel paddings."""
    return width - SKILL_PAD * 2


def skill_title_width(width: int) -> int:
    """Return measured title width reserved beside the icon and metadata, with a 96-pixel minimum."""
    return max(96, width - 214)


def skill_title_lines(draw, data: SkillData, group: SkillGroup, width: int) -> list[str]:
    """Return at most two localized title lines fitting a skill-card width."""
    return wrap_locale(
        draw, group.name, font(SKILL_TITLE_SIZE, bold=True, locale=data.locale), skill_title_width(width), data.locale
    )[:2]


def skill_header(draw, data: SkillData, group: SkillGroup, x: int, y: int, width: int) -> int:
    """Return the description start y coordinate below a measured one/two-line skill header."""
    lines = skill_title_lines(draw, data, group, width)
    extra = max(0, len(lines) - 1)
    divider = y + 56 + extra * SKILL_TITLE_STEP
    return divider + 14


def meta_label(draw, data: SkillData, text: str, x: int, y: int, *, color=PURPLE) -> int:
    """Draw a small colored metadata pill at x/y and return its measured pixel width."""
    fnt = font_w(10, WEIGHT_SEMI, data.locale)
    width = draw.textlength(text, font=fnt) + 14
    draw.rounded_rectangle(
        (x, y, x + width, y + 17), radius=7,
        fill=(*color[:3], 26), outline=(*color[:3], 68), width=1,
    )
    draw.text((x + 7, y + 3), text, font=fnt, fill=color)
    return width


def stat_value(draw, data: SkillData, label: str, value: str, x: int, y: int, width: int, *, value_color):
    """Draw a label/right-aligned skill value in pixel width, shrinking the value font to fit."""
    size = 13
    lab = font_w(size, WEIGHT_SEMI, data.locale)
    label_w = draw.textlength(label, font=lab)
    while size > 9 and draw.textlength(value, font=font_w(size, WEIGHT_REGULAR, data.locale)) > width - label_w - 16:
        size -= 1
    fnt = font_w(size, WEIGHT_REGULAR, data.locale)
    draw.text((x, y), label, font=lab, fill=MUTED)
    value_w = draw.textlength(value, font=fnt)
    draw.text((x + width - value_w, y), value, font=fnt, fill=value_color)
    draw.line((x, y + STATS_ROW - 4, x + width, y + STATS_ROW - 4), fill=(255, 255, 255, 16), width=1)


def stats_block(canvas, draw, data: SkillData, group: SkillGroup, x: int, y: int, width: int) -> int:
    """Draw energy, toughness and SP rows below a skill description; return the bottom y coordinate."""
    composite_panel(
        canvas,
        (x, y, x + width, y + STATS_H),
        10,
        (16, 12, 27, 226),
        (255, 255, 255, 22),
    )
    inner_x = x + 12
    inner_w = width - 24
    rows = (
        (ui(data, "energy"), group.energy),
        (ui(data, "toughness"), group.toughness),
        (ui(data, "sp"), group.sp_change),
    )
    for index, (label, value) in enumerate(rows):
        stat_value(
            draw, data, label, value,
            inner_x, y + 6 + index * STATS_ROW, inner_w,
            value_color=MUTED if value == DASH else VALUE,
        )
    return y + STATS_H


def measure_glossary(draw, data: SkillData, term: GlossaryTerm, width: int) -> int:
    """Return the pixel height required for a glossary title, wrapped description and padding."""
    body_w = width - GLOSSARY_INNER * 2
    lines = layout_lines(draw, glossary_tokens(term), body_w, GLOSSARY_BODY_SIZE, data.locale)
    return 22 + len(lines) * GLOSSARY_LINE + 8


def glossary_block(canvas, draw, data: SkillData, term: GlossaryTerm, x: int, y: int, width: int) -> int:
    """Draw a measured glossary panel at x/y and return its bottom y coordinate."""
    height = measure_glossary(draw, data, term, width)
    composite_panel(
        canvas,
        (x, y, x + width, y + height),
        9,
        (30, 24, 47, 238),
        (255, 255, 255, 26),
    )
    draw.text(
        (x + GLOSSARY_INNER, y + 7),
        term.name,
        font=font_w(GLOSSARY_TITLE_SIZE, WEIGHT_SEMI, data.locale),
        fill=TEXT,
    )
    lines = layout_lines(draw, glossary_tokens(term), width - GLOSSARY_INNER * 2, GLOSSARY_BODY_SIZE, data.locale)
    draw_lines(
        draw, lines, x + GLOSSARY_INNER, y + 22,
        GLOSSARY_BODY_SIZE, GLOSSARY_LINE, data.locale,
    )
    return y + height


def measure_skill_panel(draw, data: SkillData, panel: SkillPanel, width: int, body_size: int) -> int:
    """Return natural pixel height for a skill/continuation, including selected glossary/stat blocks."""
    group = panel.group
    natural = skill_header(draw, data, group, 0, 0, width)
    body_size_h = body_size + 5
    if panel.lines is not None:
        lines = panel.lines
    else:
        tokens = description_tokens(group)
        lines = trim_blank_lines(layout_lines(draw, tokens, skill_text_width(width), body_size, data.locale))
    natural += len(lines) * body_size_h + SKILL_BOTTOM + 4
    if panel.parts > 1:
        natural += 18
    if panel.extras and group.extras:
        natural += 12
        natural += sum(GLOSSARY_GAP + measure_glossary(draw, data, term, skill_text_width(width)) for term in group.extras)
    if panel.stats:
        natural += STATS_GAP + STATS_H
    return natural


def measure_skill_card(draw, data: SkillData, panel: SkillPanel, width: int, body_size: int) -> int:
    """Return the same natural pixel height used by the skill-panel drawing path."""
    return measure_skill_panel(draw, data, panel, width, body_size)


def measure_eidolon_card(draw, data: SkillData, rank: RankRow, width: int, body_size: int, extras: bool = True) -> int:
    """Return natural pixel height for eidolon text/comparison runs and optionally glossary extras."""
    natural = 54
    runs = rank.diff_runs if rank.diff_runs is not None else eidolon_tokens(rank)
    natural += measure_runs(draw, runs, width - EID_PAD * 2, body_size, body_size + 4, data.locale)[0]
    natural += EID_BOTTOM
    if extras and rank.extras:
        natural += 10
        natural += sum(GLOSSARY_GAP + measure_glossary(draw, data, term, width - EID_PAD * 2) for term in rank.extras)
    return natural


def skill_card(
    canvas,
    draw,
    data: SkillData,
    panel: SkillPanel,
    x: int,
    y: int,
    width: int,
    height: int,
    body_size: int,
    max_lines: int | None = None,
):
    """Draw a skill or continuation into the supplied pixel bounds.

    Use premeasured lines when available; otherwise wrap the resolved description.
    body_size controls readable text, max_lines optionally limits it, and only the
    last continuation carries configured glossary/stats blocks. Comparison markers
    are overlaid in place. Cached artwork/fonts may be read; no provider IO occurs.
    """
    group = panel.group
    natural = measure_skill_panel(draw, data, panel, width, body_size)
    composite_panel(canvas, (x, y, x + width, y + height), 18, CARD_FILL, CARD_EDGE)
    icon = skill_icon(data, group, 52)
    if icon:
        canvas.alpha_composite(icon, (x + 15, y + 13))
    else:
        draw.ellipse((x + 15, y + 13, x + 67, y + 65), fill=(190, 151, 255, 24), outline=(190, 151, 255, 80), width=1)
        draw.text((x + 29, y + 30), group.type_label[:3], font=font(11, bold=True), fill=PURPLE)
    text_x = x + 80
    header_label = f"{group.type_label}  /  PART {panel.part} OF {panel.parts}" if panel.parts > 1 else group.type_label
    draw.text((text_x, y + 9), header_label, font=font_w(10, WEIGHT_SEMI, data.locale), fill=PURPLE)

    title_y = y + 27
    for line in skill_title_lines(draw, data, group, width):
        title_runs(draw, line, SKILL_TITLE_SIZE, data, text_x, title_y)
        title_y += SKILL_TITLE_STEP
    level_text = f"Lv. {group.cap}" if group.level_rows and group.cap > 0 else ui(data, "passive")
    level_font = font_w(10, WEIGHT_SEMI, data.locale)
    level_w = draw.textlength(level_text, font=level_font)
    composite_panel(
        canvas,
        (x + width - level_w - 30, y + 9, x + width - 14, y + 31),
        11,
        (244, 201, 107, 18),
        (244, 201, 107, 80),
    )
    draw.text((x + width - level_w - 22, y + 14), level_text, font=level_font, fill=GOLD)


    body_y = skill_header(draw, data, group, x, y, width) + 4
    draw.line((x + 16, body_y - 16, x + width - 16, body_y - 16), fill=LINE, width=1)
    if panel.lines is not None:
        lines = panel.lines
    else:
        tokens = description_tokens(group)
        lines = trim_blank_lines(layout_lines(draw, tokens, skill_text_width(width), body_size, data.locale))
    if max_lines is not None:
        lines = lines[:max_lines]
    draw_lines(
        draw, lines, x + SKILL_PAD, body_y,
        body_size, body_size + 5, data.locale,
    )
    body_y += len(lines) * (body_size + 5)

    if panel.parts > 1:
        body_y += 10

    if panel.extras and group.extras:
        body_y += 6
        inner_w = skill_text_width(width)
        for term in group.extras:
            body_y = glossary_block(canvas, draw, data, term, x + SKILL_PAD, body_y, inner_w) + GLOSSARY_GAP
        body_y -= GLOSSARY_GAP
        body_y += 6

    if panel.stats:
        stats_y = body_y + STATS_GAP
        stats_block(canvas, draw, data, group, x + SKILL_PAD, stats_y, skill_text_width(width))
    if group.change is not None:
        change_overlay(canvas, (x, y, x + width, y + height), radius=18)
        change_badge(draw, x + width - 84, y + 35, locale=data.locale)


def eidolon_card(
    canvas,
    draw,
    data: SkillData,
    rank: RankRow,
    x: int,
    y: int,
    width: int,
    height: int,
    body_size: int,
    max_lines: int | None = None,
    extras: bool = True,
):
    """Draw one eidolon into supplied pixel bounds, including its cached artwork.

    body_size selects text pixels; max_lines optionally limits description rows and
    extras controls glossary blocks. Draw previous/current icons and comparison
    highlights when available. Mutate canvas/draw only; no provider requests occur.
    """
    natural = measure_eidolon_card(draw, data, rank, width, body_size)
    composite_panel(canvas, (x, y, x + width, y + height), 16, CARD_FILL, CARD_EDGE)
    icon = previous_eidolon_icon(data, rank, 40)
    if icon:
        canvas.alpha_composite(icon, (x + 14, y + 11))
    else:
        draw.ellipse((x + 14, y + 11, x + 54, y + 51), fill=(190, 151, 255, 28), outline=(190, 151, 255, 95), width=1)
        draw.text((x + 20, y + 22), "PREV", font=font(9, bold=True), fill=PURPLE)
    text_x = x + 64
    draw.text((text_x, y + 8), f"E{rank.key}", font=font_w(10, WEIGHT_SEMI, data.locale), fill=PURPLE)
    title_width = width - 78 - 48
    title = fit(draw, rank.name, font(EID_TITLE_SIZE, bold=True, locale=data.locale), title_width)
    title_runs(draw, title, EID_TITLE_SIZE, data, text_x, y + 24)
    current = eidolon_icon(data, rank, 40)
    if current:
        canvas.alpha_composite(current, (x + width - 54, y + 11))
    else:
        draw.ellipse((x + width - 54, y + 11, x + width - 14, y + 51), fill=(190, 151, 255, 22), outline=(190, 151, 255, 80), width=1)
        draw.text((x + width - 46, y + 26), str(rank.key), font=font(11, bold=True), fill=PURPLE)
    draw.line((x + 14, y + 50, x + width - 14, y + 50), fill=LINE, width=1)
    body_y = y + 54
    runs = rank.diff_runs if rank.diff_runs is not None else eidolon_tokens(rank)
    body_y += draw_lines(
        draw,
        layout_lines(draw, runs, width - EID_PAD * 2, body_size, data.locale),
        x + EID_PAD,
        body_y,
        body_size,
        body_size + 4,
        data.locale,
        max_lines=max_lines,
    )
    if extras and rank.extras and max_lines is None:
        body_y += 10
        inner_w = width - EID_PAD * 2
        for term in rank.extras:
            body_y = glossary_block(canvas, draw, data, term, x + EID_PAD, body_y, inner_w) + GLOSSARY_GAP
        body_y -= GLOSSARY_GAP
    if rank.change is not None:
        change_overlay(canvas, (x, y, x + width, y + height), radius=16)
        change_badge(draw, x + width - 84, y + 35, locale=data.locale)
