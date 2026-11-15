"""Draw ascension and trace costs, including added and removed materials."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import GOLD
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import composite_panel
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.character_info import material_name
from hsr_cards.renderer.nanoka.info.drawing import _strike, change_overlay, heading
from hsr_cards.renderer.nanoka.info.models import CardData
from hsr_cards.renderer.nanoka.info.styles import ADDED_COLOR, ARROW_COLOR, CARD_EDGE, CARD_FILL, CONTENT_W, M, REMOVED_COLOR
from hsr_cards.renderer.nanoka.info.text import fit, heavy, text_locale, ui


def _amount(value: int) -> str:
    return f"x{value:,}"


def _credits_value(draw, x, y, width, amount, old_amount, locale: str) -> None:
    """Draw credits, adding the struck old total before an arrow when changed."""
    new_font = heavy(36, locale, display=True)
    new_text = f"{amount:,}"
    new_w = draw.textlength(new_text, font=new_font)
    if old_amount is None or old_amount == amount:
        draw.text((x, y + 20), new_text, font=new_font, fill=TEXT)
        return
    old_font = heavy(21, locale, display=True)
    old_text = f"{old_amount:,}"
    old_w = draw.textlength(old_text, font=old_font)
    arrow_font = heavy(19, locale, display=True)
    arrow_w = draw.textlength("\u2192", font=arrow_font)
    gap = 10
    total = old_w + gap + arrow_w + gap + new_w
    start = x
    if total > width:
        start = x
    old_y = y + 28
    draw.text((start, old_y), old_text, font=old_font, fill=REMOVED_COLOR)
    _strike(draw, start, old_y + 14, old_w, REMOVED_COLOR, 18)
    draw.text((start + old_w + gap, y + 26), "\u2192", font=arrow_font, fill=ARROW_COLOR)
    draw.text((start + old_w + gap + arrow_w + gap, y + 20), new_text, font=new_font, fill=TEXT)


def compact_rows(rows, limit: int = 8):
    """Prioritize material rows with previous/change metadata, then fill the grid from remaining rows up to limit."""
    changed = [row for row in rows if row[1] is not None or row[2] or row[3]]
    if len(changed) >= limit:
        return changed[:limit]
    ordered = list(changed)
    for row in rows:
        if row not in ordered:
            ordered.append(row)
        if len(ordered) >= limit:
            break
    return ordered


def credits_strip(canvas, draw, data: CardData, x, y, width, amount, before_amount=None):
    """Draw localized credit totals, optional previous-to-current values, cached credit icon and a divider in pixel bounds."""
    draw.text((x, y), ui(data, "total_credits"), font=font(14, bold=True, locale=data.locale), fill=DIM)
    _credits_value(draw, x, y, width, amount, before_amount, data.locale)
    icon = load_webp(data.icons.get(2), (42, 42))
    if icon:
        canvas.alpha_composite(icon, (x + width - 46, y + 16))
    draw.line((x, y + 70, x + width, y + 70), fill=LINE, width=1)


def material_item(canvas, draw, data: CardData, x, y, width, cost, icon_size, name_size, stacked=False, before_amount=None, added=False, removed=False):
    """Draw one material icon/name/quantity within the supplied pixel width.

    icon_size/name_size set pixel sizing; stacked chooses the name/quantity layout.
    before_amount/added/removed control comparison markers and strike removed rows.
    Read cached artwork only and mutate the canvas/draw in place.
    """
    icon = load_webp(data.icons.get(cost.item_id), (icon_size, icon_size))
    if icon:
        canvas.alpha_composite(icon, (x, y))
    name = material_name(data.items, cost.item_id, data.locale)
    name_f = font(name_size, bold=True, locale=text_locale(name, data.locale))
    qty_f = heavy(name_size + 1, data.locale)
    if added:
        name = f"+ {name}"
    name_color = ADDED_COLOR if added else (REMOVED_COLOR if removed else TEXT)
    qty = _amount(cost.amount)
    if stacked:
        draw.text((x + icon_size + 12, y - 2), fit(draw, name, name_f, width - icon_size - 18), font=name_f, fill=name_color)
        draw.text((x + icon_size + 12, y + name_size + 8), qty, font=qty_f, fill=GOLD)
        if removed:
            _strike(draw, x + icon_size + 12, y + name_size + 16, draw.textlength(qty, font=qty_f), GOLD, name_size)
        return
    if before_amount is not None and before_amount != cost.amount:
        old_font = heavy(name_size - 3, data.locale)
        old_text = _amount(before_amount)
        old_w = draw.textlength(old_text, font=old_font)
        new_w = draw.textlength(qty, font=qty_f)
        arrow_font = font(name_size - 4, bold=True, locale=data.locale)
        arrow_w = draw.textlength("\u2192", font=arrow_font)
        gap = 6
        qty_block = old_w + gap + arrow_w + gap + new_w
        name_width = width - icon_size - 20 - qty_block
        draw.text((x + icon_size + 12, y + 1), fit(draw, name, name_f, name_width), font=name_f, fill=name_color)
        qx = x + width - qty_block
        draw.text((qx, y + 5), old_text, font=old_font, fill=REMOVED_COLOR)
        _strike(draw, qx, y + 13, old_w, REMOVED_COLOR, name_size)
        draw.text((qx + old_w + gap, y + 3), "\u2192", font=arrow_font, fill=ARROW_COLOR)
        draw.text((qx + old_w + gap + arrow_w + gap, y + 1), qty, font=qty_f, fill=ADDED_COLOR)
        return
    qty_w = draw.textlength(qty, font=qty_f)
    draw.text((x + icon_size + 12, y + 1), fit(draw, name, name_f, width - icon_size - 28 - qty_w), font=name_f, fill=name_color)
    draw.text((x + width - qty_w, y + 1), qty, font=qty_f, fill=ADDED_COLOR if added else (REMOVED_COLOR if removed else GOLD))
    if removed:
        _strike(draw, x + icon_size + 12, y + 11, min(draw.textlength(name, font=name_f), width - icon_size - 28 - qty_w), name_color, name_size)
        _strike(draw, x + width - qty_w, y + 11, qty_w, REMOVED_COLOR, name_size)


def compare_costs(before, after):
    """Return (cost, previous amount, added, removed) rows, listing newer costs first and removed costs afterward."""
    old = {cost.item_id: cost.amount for cost in before}
    new = {cost.item_id: cost.amount for cost in after}
    rows = []
    for cost in after:
        rows.append((cost, old.get(cost.item_id), cost.item_id not in old, False))
    for cost in before:
        if cost.item_id not in new:
            rows.append((cost, cost.amount, False, True))
    return rows


def ascension_panel(canvas, draw, data: CardData, y: int, height: int, icon_size: int, name_size: int):
    """Draw ascension costs/credit totals in the supplied pixel height, including optional material comparisons."""
    heading(draw, M, y, ui(data, "ascension"), ui(data, "level_range"), CONTENT_W, data.locale)
    composite_panel(canvas, (M, y + 48, 1080 - M, y + 48 + height), 24, CARD_FILL, CARD_EDGE)
    before_credits = next((cost.amount for cost in data.before.ascension if cost.item_id == 2), 0) if data.before is not None else None
    credits = next((cost.amount for cost in data.ascension if cost.item_id == 2), 0)
    credits_strip(canvas, draw, data, M + 28, y + 62, CONTENT_W - 56, credits, before_credits)
    rows = compare_costs(data.before.ascension, data.ascension) if data.before is not None else [(cost, None, False, False) for cost in data.ascension]
    items = [row for row in rows if row[0].item_id != 2]
    col_w = (CONTENT_W - 56) / 2
    row_h = 72
    visible = compact_rows(items, 4) if data.before is not None else items[:4]
    changed_credits = before_credits is not None and before_credits != credits
    if changed_credits:
        change_overlay(canvas, (M + 20, y + 54, 1080 - M - 20, y + 132), radius=16)
    for i, (cost, old_amount, added, removed) in enumerate(visible):
        col = i % 2
        row = i // 2
        item_x = round(M + 28 + col * col_w)
        item_y = round(y + 148 + row * row_h)
        if (old_amount is not None and old_amount != cost.amount) or added or removed:
            change_overlay(canvas, (item_x - 6, item_y - 4, item_x + col_w - 16, item_y + 58), radius=12)
        material_item(canvas, draw, data, item_x, item_y, round(col_w - 22), cost, icon_size, name_size, stacked=False, before_amount=old_amount, added=added, removed=removed)


def skills_panel(canvas, draw, data: CardData, y: int, height: int, icon_size: int, name_size: int, row_h: int = 62):
    """Draw skill/trace material totals in the supplied pixel height, with configurable row spacing and comparisons."""
    heading(draw, M, y, ui(data, "skills"), ui(data, "all_skills"), CONTENT_W, data.locale)
    composite_panel(canvas, (M, y + 48, 1080 - M, y + 48 + height), 24, CARD_FILL, CARD_EDGE)
    before_credits = next((cost.amount for cost in data.before.skills if cost.item_id == 2), 0) if data.before is not None else None
    credits = next((cost.amount for cost in data.skills if cost.item_id == 2), 0)
    credits_strip(canvas, draw, data, M + 28, y + 62, CONTENT_W - 56, credits, before_credits)
    rows = compare_costs(data.before.skills, data.skills) if data.before is not None else [(cost, None, False, False) for cost in data.skills]
    items = [row for row in rows if row[0].item_id != 2]
    if data.before is not None:
        items = compact_rows(items, 8)
    columns = (len(items) + 1) // 2
    col_w = (CONTENT_W - 56) / 2
    changed_credits = before_credits is not None and before_credits != credits
    if changed_credits:
        change_overlay(canvas, (M + 20, y + 54, 1080 - M - 20, y + 132), radius=16)
    for i, (cost, old_amount, added, removed) in enumerate(items):
        col = i // columns
        row = i % columns
        item_x = round(M + 28 + col * col_w)
        item_y = round(y + 148 + row * row_h)
        if (old_amount is not None and old_amount != cost.amount) or added or removed:
            change_overlay(canvas, (item_x - 6, item_y - 4, item_x + col_w - 16, item_y + row_h - 12), radius=12)
        material_item(canvas, draw, data, item_x, item_y, round(col_w - 24), cost, icon_size, name_size, stacked=False, before_amount=old_amount, added=added, removed=removed)

    heading(draw, M, y, ui(data, "skills"), ui(data, "all_skills"), CONTENT_W, data.locale)
    composite_panel(canvas, (M, y + 48, 1080 - M, y + 48 + height), 24, CARD_FILL, CARD_EDGE)
    before_credits = next((cost.amount for cost in data.before.skills if cost.item_id == 2), 0) if data.before is not None else None
    credits = next((cost.amount for cost in data.skills if cost.item_id == 2), 0)
    credits_strip(canvas, draw, data, M + 28, y + 62, CONTENT_W - 56, credits, before_credits)
    rows = compare_costs(data.before.skills, data.skills) if data.before is not None else [(cost, None, False, False) for cost in data.skills]
    items = [row for row in rows if row[0].item_id != 2]
    if data.before is not None:
        items = compact_rows(items, 8)
    columns = (len(items) + 1) // 2
    for i, (cost, old_amount, added, removed) in enumerate(items):
        col = i // columns
        row = i % columns
        material_item(canvas, draw, data, round(M + 28 + col * col_w), round(y + 148 + row * row_h), round(col_w - 24), cost, icon_size, name_size, stacked=False, before_amount=old_amount, added=added, removed=removed)


def comparison_rows(costs, before_costs, limit=None):
    """Return newer-first material comparison tuples followed by removals, optionally capped to limit rows."""
    rows = compare_costs(before_costs, costs)
    return rows[:limit] if limit is not None else rows
