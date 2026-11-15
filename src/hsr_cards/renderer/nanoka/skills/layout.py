"""Plan skill sections and keep split skill parts together in each column."""
from __future__ import annotations

import math
from hsr_cards.renderer.nanoka.skills.cards import measure_eidolon_card, measure_glossary, measure_skill_card, skill_header, skill_text_width
from hsr_cards.renderer.nanoka.skills.header import ui
from hsr_cards.renderer.nanoka.skills.models import Piece, SkillData, SkillGroup, SkillPanel
from hsr_cards.renderer.nanoka.skills.preparation import group_columns, normalize_breaks
from hsr_cards.renderer.nanoka.skills.styles import BODY_SOFT, BOTTOM_RESERVE, CONTENT_TOP, DESC_SPLIT_H, DESC_TARGET_H, EID_GAP, GAP, GLOSSARY_GAP, H, LEFT_W, MAX_PAGE_H, MAX_PARTS, RIGHT_W, ROW_GAP, SECTION_GAP, SECTION_HEAD_H, STATS_GAP, STATS_H, VALUE, WEIGHT_REGULAR
from hsr_cards.renderer.nanoka.skills.text import desc_tokens, layout_lines, trim_blank_lines


def skill_sections(data: SkillData) -> list[tuple[str, list[SkillGroup], str]]:
    """Group resolved skills into localized character/memosprite sections with display subtitles."""
    combat = [group for group in data.skills if group.scope == "character"]
    memo = [group for group in data.skills if group.scope == "memosprite"]
    sections: list[tuple[str, list[SkillGroup], str]] = []
    if combat:
        sections.append((ui(data, "skills"), combat, f"{len(combat)} SKILLS"))
    if memo:
        subtitle = f"{data.memosprite_name.upper()}  /  {len(memo)} SKILLS" if data.memosprite_name else f"{len(memo)} SKILLS"
        sections.append((ui(data, "memosprite"), memo, subtitle))
    return sections


def closest_cut(cuts: list[int], value: int) -> int:
    """Return the minimum distance from value to candidate cut offsets; empty cuts raises ValueError."""
    return min(abs(value - cut) for cut in cuts)


def sentence_cuts(raw: str, spaces: list[int]) -> list[int]:
    """Prefer places right after sentence punctuation (outside markup)."""
    result = []
    for index in spaces:
        prefix = raw[:index].rstrip()
        if prefix and prefix[-1] in ".!?":
            result.append(index)
    return result


def safe_cuts(raw: str) -> list[int]:
    """Space offsets that never fall inside Nanoka markup."""
    result = []
    depth = 0
    for index, char in enumerate(raw):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif char == " " and depth == 0 and index > 0:
            result.append(index)
    return result


def _chunk_lines(lines: list[list[Piece]], parts: int) -> list[list[list[Piece]]]:
    """Split laid-out lines into balanced chunks, preferring sentence ends."""
    if parts <= 1 or len(lines) <= 1:
        return [lines]
    total = len(lines)
    step = total / parts
    boundaries = [0]
    for part in range(1, parts):
        target = round(step * part)
        window = max(2, round(step * 0.35))
        best = None
        for candidate in range(max(1, target - window), min(total, target + window + 1)):
            score = abs(candidate - target)
            previous = "".join(piece.text for piece in lines[candidate - 1]).strip()
            if previous.endswith((".", "!", "?")):
                score -= step * 0.6
            if best is None or score < best[0]:
                best = (score, candidate)
        boundary = best[1] if best else target
        if boundary > boundaries[-1]:
            boundaries.append(boundary)
    boundaries.append(total)
    return [lines[boundaries[index]:boundaries[index + 1]] for index in range(len(boundaries) - 1)]


def split_group(data: SkillData, draw, group: SkillGroup, width: int, body_size: int) -> list[SkillPanel]:
    """Split very long descriptions into readable, balanced cards.

    Splitting happens on the laid-out line list, so every part is rendered
    from the exact same rich-text pieces as the unsplit card. Parts after the
    first start with a continuation marker and only the final part carries
    the glossary and stats block.
    """
    raw = normalize_breaks(group.raw_desc or group.desc or "")
    tokens = desc_tokens(raw, {row.index: row for row in group.rows}, VALUE, group_columns(group))
    lines = trim_blank_lines(layout_lines(draw, tokens, skill_text_width(width), body_size, data.locale))
    line_h = body_size + 5
    total_h = len(lines) * line_h
    if total_h <= DESC_SPLIT_H:
        return [SkillPanel(group=group, desc=raw, part=1, parts=1)]

    glossary_h = 12 + sum(
        GLOSSARY_GAP + measure_glossary(draw, data, term, skill_text_width(width))
        for term in group.extras
    ) if group.extras else 0
    stats_h = STATS_GAP + STATS_H
    body_start = skill_header(draw, data, group, 0, 0, width)
    card_cap = DESC_TARGET_H + body_start + glossary_h + stats_h + 40
    total_card_h = body_start + total_h + glossary_h + stats_h
    parts = min(MAX_PARTS, max(2, math.ceil(total_card_h / card_cap)))

    chunks = _chunk_lines(lines, parts)
    if len(chunks) < 2:
        return [SkillPanel(group=group, desc=raw, part=1, parts=1)]

    panels = []
    for index, chunk in enumerate(chunks):
        chunk = list(chunk)
        if index > 0 and chunk:
            first = chunk[0]
            marker = Piece("\u2026 ", BODY_SOFT, WEIGHT_REGULAR)
            chunk[0] = [marker] + first
        panels.append(
            SkillPanel(
                group=group,
                desc=raw,
                part=index + 1,
                parts=len(chunks),
                extras=index == len(chunks) - 1,
                stats=index == len(chunks) - 1,
                lines=chunk,
            )
        )
    return panels


def masonry_columns(heights: list[int], cols: int, gap: int) -> list[float]:
    """Assign cards to the shortest column; keeps reading order per column."""
    sums = [0.0] * cols
    for height in heights:
        index = sums.index(min(sums))
        sums[index] += height + gap
    return sums


def slot_groups(panels: list[SkillPanel], heights: list[int]) -> list[list[int]]:
    """Group split parts so "Part 1/2" and "Part 2/2" stay together.

    A group occupies one masonry slot and its panels render one after another
    inside that slot; parts never land in different columns.
    """
    groups: list[list[int]] = []
    for index, panel in enumerate(panels):
        if panel.part > 1 and groups:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def section_layout(data: SkillData, draw, groups: list[SkillGroup], body_size: int, cols: int, left_w: int) -> dict:
    """Measure a skill section into cols masonry columns of the available pixel width.

    Return a plan with panel widths/heights, grouped continuation indices, column
    heights, total height and layout cost. Split parts retain the same masonry slot.
    The function measures fonts/text only and does not draw or request provider data.
    """
    width = (left_w - GAP * (cols - 1)) // cols
    panels: list[SkillPanel] = []
    base_heights = []
    for group in groups:
        group_panels = split_group(data, draw, group, width, body_size)
        base_heights.append(measure_skill_card(draw, data, group_panels[0], width, body_size))
        panels.extend(group_panels)
    heights = [measure_skill_card(draw, data, panel, width, body_size) for panel in panels]
    groups_index = slot_groups(panels, heights)
    group_heights = [
        sum(heights[index] for index in indices) + ROW_GAP * max(0, len(indices) - 1)
        for indices in groups_index
    ]
    sums = masonry_columns(group_heights, cols, ROW_GAP)
    column_heights = [0.0] * cols
    for indices, height in zip(groups_index, group_heights):
        slot = column_heights.index(min(column_heights))
        column_heights[slot] += height + ROW_GAP
    total = math.ceil(max(column_heights)) if column_heights else 0
    imbalance = (max(column_heights) - min(column_heights)) / (max(column_heights) or 1) if column_heights else 0.0
    cards = len(panels) or 1
    orphan = 0.05 if cards < cols else 0.0
    short_cards = sum(1 for height in base_heights if height < 260)
    short_penalty = short_cards * 0.04
    cost = total * (1.0 + imbalance * 0.45 + orphan + short_penalty)
    return {
        "cols": cols, "width": width, "panels": panels, "heights": heights,
        "groups": groups_index, "group_heights": group_heights,
        "columns": column_heights, "total": total, "cost": cost,
    }


def best_section_layout(data: SkillData, draw, groups: list[SkillGroup], body_size: int, left_w: int) -> dict:
    """Return the fixed two-column section plan for the requested text size and available width."""
    return section_layout(data, draw, groups, body_size, 2, left_w)


def is_large_frame(data: SkillData, height: int) -> bool:
    """Return whether the planned canvas exceeds 1900 pixels in height."""
    return height > 1900


def body_sizes(data: SkillData, height: int) -> tuple[int, ...]:
    """Return descending candidate body font sizes, adding 19 pixels for large frames."""
    if is_large_frame(data, height):
        return (19, 18, 17, 16, 15, 14, 13)
    return (18, 17, 16, 15, 14, 13)


def eidolon_heights(data: SkillData, draw, body_size: int, width: int = RIGHT_W) -> list[int]:
    """Measure every resolved eidolon at body_size/width pixels in data order."""
    return [measure_eidolon_card(draw, data, rank, width, body_size) for rank in data.eidolons]


def distribute_even(item_heights: list[int], gap: int, available: int) -> tuple[list[int], int]:
    """Keep cards at their natural heights; unused space stays below the stack."""
    return list(item_heights), gap


def plan_page(data: SkillData, draw) -> dict:
    """Pick font sizes and section layout, growing the canvas for long kits."""
    sections = skill_sections(data)
    chosen = None
    sizes = body_sizes(data, H)
    for body_size in sizes:
        layouts = [best_section_layout(data, draw, groups, body_size, LEFT_W) for _, groups, _ in sections]
        left_total = sum(layout["total"] for layout in layouts) + SECTION_GAP * max(0, len(layouts) - 1)
        left_total += SECTION_HEAD_H * len(layouts)
        eid_size = max(13, body_size - 2)
        eid_heights = eidolon_heights(data, draw, eid_size)
        eid_total = sum(eid_heights) + EID_GAP * max(0, len(eid_heights) - 1)
        height = max(H, CONTENT_TOP + max(left_total, eid_total) + BOTTOM_RESERVE + 10)
        if height > MAX_PAGE_H:
            continue
        chosen = {
            "body": body_size, "eid": eid_size, "height": height,
            "sections": sections, "layouts": layouts, "eid_heights": eid_heights,
        }
        break

    if chosen is None:
        body_size = 13
        layouts = [best_section_layout(data, draw, groups, body_size, LEFT_W) for _, groups, _ in sections]
        left_total = sum(layout["total"] for layout in layouts) + SECTION_GAP * max(0, len(layouts) - 1)
        left_total += SECTION_HEAD_H * len(layouts)
        eid_size = 13
        eid_heights = eidolon_heights(data, draw, eid_size)
        eid_total = sum(eid_heights) + EID_GAP * max(0, len(eid_heights) - 1)
        height = max(H, CONTENT_TOP + max(left_total, eid_total) + BOTTOM_RESERVE + 10)
        chosen = {
            "body": body_size, "eid": eid_size, "height": height,
            "sections": sections, "layouts": layouts, "eid_heights": eid_heights,
        }
    return chosen
