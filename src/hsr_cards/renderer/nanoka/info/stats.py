"""Draw base stats, trace bonuses, and localized voice credits."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import PURPLE
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import clean_localized
from hsr_cards.renderer.nanoka.character_info import composite_panel
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import format_bonus
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.info.drawing import _strike, change_overlay
from hsr_cards.renderer.nanoka.info.models import CardData
from hsr_cards.renderer.nanoka.info.styles import ARROW_COLOR, BASIC_STAT_ICONS, BONUS_ICONS, CARD_EDGE, CARD_FILL, M, REMOVED_COLOR
from hsr_cards.renderer.nanoka.info.text import fit, heavy, text_locale, ui


def stat_icon(data: CardData, name: str, size: int = 24):
    """Read a cached stat icon at size square pixels; missing/unreadable artwork returns None."""
    path = data.icon_dir / name if data.icon_dir else None
    return load_webp(path, (size, size))


def bonus_icon_name(label: str) -> str | None:
    """Map an English trace-bonus label to its icon filename, or None when unmapped."""
    return BONUS_ICONS.get(label)


def stat_row(canvas, draw, data: CardData, x, y, width, label, value, icon_name=None, value_size=22, icon_size=24, before_value=None):
    """Draw a stat label/icon/value in pixel bounds, displaying and highlighting differing previous values."""
    icon = stat_icon(data, icon_name, icon_size) if icon_name else None
    text_x = x
    if icon:
        canvas.alpha_composite(icon, (round(x), round(y - 2)))
        text_x += icon_size + 12
    else:
        draw.ellipse((x + 5, y + 8, x + 13, y + 16), fill=(255, 255, 255, 30))
        text_x += icon_size + 12
    label_font = font(17, bold=True, locale=data.locale)
    value_locale = text_locale(str(value), data.locale)
    value_font = heavy(value_size, value_locale, display=True)
    if before_value is None or before_value == value:
        draw.text((text_x, y), fit(draw, label, label_font, width - (text_x - x) - 110), font=label_font, fill=MUTED)
        value_width = draw.textlength(value, font=value_font)
        draw.text((x + width - value_width, y - 3), value, font=value_font, fill=TEXT)
    else:
        old_locale = text_locale(str(before_value), data.locale)
        old_font = heavy(max(12, value_size - 3), old_locale, display=True)
        arrow_font = font(max(11, value_size - 6), bold=True, locale=data.locale)
        old_w = draw.textlength(before_value, font=old_font)
        new_w = draw.textlength(value, font=value_font)
        arrow_w = draw.textlength("\u2192", font=arrow_font)
        gap = 6
        block = old_w + gap + arrow_w + gap + new_w
        draw.text((text_x, y), fit(draw, label, label_font, max(60, width - (text_x - x) - block - 10)), font=label_font, fill=MUTED)
        qx = x + width - block
        draw.text((qx, y + 2), before_value, font=old_font, fill=REMOVED_COLOR)
        _strike(draw, qx, y + 10, old_w, REMOVED_COLOR, value_size)
        draw.text((qx + old_w + gap, y + 1), "\u2192", font=arrow_font, fill=ARROW_COLOR)
        draw.text((qx + old_w + gap + arrow_w + gap, y - 3), value, font=value_font, fill=TEXT)
    draw.line((x, y + 34, x + width, y + 34), fill=(255, 255, 255, 20), width=1)
    if before_value is not None and before_value != value:
        change_overlay(canvas, (x - 4, y - 4, x + width + 4, y + 36), radius=10)


def draw_stats_panel(canvas, draw, data: CardData, y: int, compact: bool = False):
    """Draw base stats, bonus traces and voice labels at y; compact selects the denser pixel layout."""
    panel_h = 310 if compact else 320
    composite_panel(canvas, (M, y, 1080 - M, y + panel_h), 24, CARD_FILL, CARD_EDGE)
    col_gap = 28
    inner_w = 1080 - M * 2 - 56 - col_gap * 2
    col_w = inner_w / 3
    col1 = M + 28
    col2 = col1 + col_w + col_gap
    col3 = col2 + col_w + col_gap
    for line_x in (col1 + col_w + col_gap / 2, col2 + col_w + col_gap / 2):
        draw.line((line_x, y + 24, line_x, y + panel_h - 24), fill=(255, 255, 255, 38), width=1)
    header_y = y + 20
    draw.text((col1, header_y), ui(data, "base_stats"), font=heavy(16, data.locale), fill=PURPLE)
    draw.text((col2, header_y), ui(data, "trace_stat_bonus"), font=heavy(16, data.locale), fill=PURPLE)
    draw.text((col3, header_y), ui(data, "voice_cast"), font=heavy(16, data.locale), fill=PURPLE)
    draw.line((col1, y + 48, 1080 - M - 28, y + 48), fill=LINE, width=1)
    def voice_text(raw):
        if not raw:
            return ""
        value = str(raw).replace("\\n", " ").replace("\n", " ")
        return " ".join(value.split())

    before = data.before
    base_specs = [
        ("hp", ui(data, "base_hp"), "hp", BASIC_STAT_ICONS["hp"]),
        ("atk", ui(data, "base_atk"), "atk", BASIC_STAT_ICONS["atk"]),
        ("def", ui(data, "base_def"), "def", BASIC_STAT_ICONS["def"]),
        ("spd", ui(data, "base_spd"), "spd", BASIC_STAT_ICONS["spd"]),
        ("aggro", ui(data, "taunt"), "aggro", None),
        ("sp_need", ui(data, "max_energy"), "sp_need", None),
    ]
    rows1 = []
    for key, label, stat_key, icon_name in base_specs:
        if key == "sp_need":
            current = data.sp_need or 0
            previous = before.sp_need if before is not None else None
            value = f"{current:g}"
            old_value = f"{previous:g}" if previous is not None and previous != current else None
        elif key in {"hp", "atk", "def"}:
            value = f"{data.stats[stat_key]:,.0f}"
            old_value = f"{before.stats[stat_key]:,.0f}" if before is not None and before.stats[stat_key] != data.stats[stat_key] else None
        else:
            value = f"{data.stats[stat_key]:g}"
            old_value = f"{before.stats[stat_key]:g}" if before is not None and before.stats[stat_key] != data.stats[stat_key] else None
        rows1.append((label, value, icon_name, old_value))
    row_h = (panel_h - 72) / max(len(rows1), 1)
    for i, (label, value, icon_name, old_value) in enumerate(rows1):
        stat_row(canvas, draw, data, col1, y + 60 + i * row_h, col_w, label, value, icon_name, 21 if compact else 22, 24, old_value)
    bonus_rows = []
    if before is None:
        for label, value, property_type in data.bonuses[:6]:
            bonus_rows.append((label.upper(), format_bonus(value, property_type), bonus_icon_name(label), None))
    else:
        old_bonuses = {label: (value, property_type) for label, value, property_type in before.bonuses}
        new_bonuses = {label: (value, property_type) for label, value, property_type in data.bonuses}
        labels = list(new_bonuses)
        labels.extend(label for label in old_bonuses if label not in new_bonuses)
        for label in labels[:6]:
            current = new_bonuses.get(label)
            previous = old_bonuses.get(label)
            if current is None:
                bonus_rows.append((label.upper(), format_bonus(*previous), bonus_icon_name(label), "removed"))
            elif previous is not None and previous[0] != current[0]:
                bonus_rows.append((label.upper(), format_bonus(*current), bonus_icon_name(label), format_bonus(*previous)))
            else:
                bonus_rows.append((label.upper(), format_bonus(*current), bonus_icon_name(label), None))
    row_h2 = (panel_h - 72) / max(len(bonus_rows), 1)
    for i, (label, value, icon_name, old_value) in enumerate(bonus_rows):
        if old_value == "removed":
            stat_row_removed(canvas, draw, data, col2, y + 60 + i * row_h2, col_w, label, value, icon_name, 21 if compact else 22, 24)
        else:
            stat_row(canvas, draw, data, col2, y + 60 + i * row_h2, col_w, label, value, icon_name, 21 if compact else 22, 24, old_value)
    va = data.detail.chara_info.va
    old_va = before.detail.chara_info.va if before is not None else None
    voices = [
        ("EN", va.english, old_va.english if old_va else None),
        ("ZH", va.chinese, old_va.chinese if old_va else None),
        ("JA", va.japanese, old_va.japanese if old_va else None),
        ("KO", va.korean, old_va.korean if old_va else None),
    ]
    voice_row_h = (panel_h - 72) / 4
    for i, (label, value, old_value) in enumerate(voices):
        text = voice_text(clean_localized(value, data.locale)) or ui(data, "not_credited")
        old_text = voice_text(clean_localized(old_value, data.locale)) or ui(data, "not_credited") if old_va is not None else None
        if old_text == text:
            old_text = None
        stat_row(canvas, draw, data, col3, y + 60 + i * voice_row_h, col_w, label, text, None, 17 if compact else 18, 24, old_text)


def stat_row_removed(canvas, draw, data: CardData, x, y, width, label, value, icon_name=None, value_size=22, icon_size=24):
    """A bonus that disappeared in the newer build: muted label and struck value."""
    icon = stat_icon(data, icon_name, icon_size) if icon_name else None
    text_x = x
    if icon:
        canvas.alpha_composite(icon, (round(x), round(y - 2)))
        text_x += icon_size + 12
    else:
        draw.ellipse((x + 5, y + 8, x + 13, y + 16), fill=(255, 255, 255, 30))
        text_x += icon_size + 12
    label_font = font(17, bold=True, locale=data.locale)
    value_font = heavy(value_size, data.locale, display=True)
    draw.text((text_x, y), fit(draw, label, label_font, width - (text_x - x) - 110), font=label_font, fill=REMOVED_COLOR)
    value_font = heavy(value_size, text_locale(str(value), data.locale), display=True)
    value_width = draw.textlength(value, font=value_font)
    vx = x + width - value_width
    draw.text((vx, y - 3), value, font=value_font, fill=REMOVED_COLOR)
    _strike(draw, vx, y + 7, value_width, REMOVED_COLOR, value_size)
    draw.line((x, y + 34, x + width, y + 34), fill=(255, 255, 255, 20), width=1)
    if before_value is not None and before_value != value:
        change_overlay(canvas, (x - 4, y - 4, x + width + 4, y + 36), radius=10)


def draw_compact_stats_panel(canvas, draw, data: CardData, y: int):
    """Draw large HP/ATK/DEF totals plus compact bonus/combat stats in the 250-pixel panel at y."""
    panel_h = 250
    composite_panel(canvas, (M, y, 1080 - M, y + panel_h), 24, CARD_FILL, CARD_EDGE)
    sx, sy = M + 30, y + 24
    primary = [(ui(data, "hp"), round(data.stats["hp"])), (ui(data, "atk"), round(data.stats["atk"])), (ui(data, "def"), round(data.stats["def"]))]
    for i, (label, value) in enumerate(primary):
        cx = sx + i * 178
        draw.text((cx, sy), label, font=heavy(17, data.locale), fill=DIM)
        draw.text((cx, sy + 24), f"{value:,}", font=heavy(56, data.locale, display=True), fill=TEXT, stroke_width=1, stroke_fill=TEXT)
    draw.text((M + 624, sy), ui(data, "stat_bonus"), font=heavy(15, data.locale), fill=PURPLE)
    for i, (label, value, property_type) in enumerate(data.bonuses[:3]):
        cy = sy + 34 + i * 44
        draw.text((M + 624, cy), label.upper(), font=heavy(12, data.locale), fill=DIM)
        draw.text((M + 842, cy - 5), format_bonus(value, property_type), font=heavy(28, data.locale, display=True), fill=TEXT if i < 2 else PURPLE)
    div_y = y + 180
    draw.line((sx, div_y, 1080 - M - 30, div_y), fill=LINE, width=1)
    secondary = [(ui(data, "spd"), f'{data.stats["spd"]:g}'), (ui(data, "crit_rate"), f'{data.stats["crit"]:g}%'), (ui(data, "crit_dmg"), f'{data.stats["crit_dmg"]:g}%'), (ui(data, "aggro"), f'{data.stats["aggro"]:g}')]
    for i, (label, value) in enumerate(secondary):
        cx = sx + i * 156
        draw.text((cx, div_y + 20), label, font=heavy(12, data.locale), fill=DIM)
        draw.text((cx, div_y + 40), value, font=heavy(28, data.locale, display=True), fill=TEXT)
