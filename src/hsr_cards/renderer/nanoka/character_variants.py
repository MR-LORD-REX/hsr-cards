from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .data import CharacterData, load_character, prime_assets
from .diff import diff_words
from .character_info import (
    BG,
    BONUS_LABELS,
    DIM,
    FIRE,
    GOLD,
    LINE,
    MUTED,
    PURPLE,
    TEXT,
    aggregate,
    asset,
    bonus_stats,
    format_bonus,
    clean_localized,
    composite_panel,
    font,
    load_webp,
    make_star,
    material_name,
    max_stats,
    radial,
    skill_materials,
    wrap,
)

M = 48
CONTENT_W = 1080 - M * 2
CARD_FILL = (23, 18, 36, 235)
CARD_EDGE = (255, 255, 255, 34)
SOFT_EDGE = (255, 255, 255, 18)

ELEMENT_LABELS = {
    "en": {"fire": "Fire", "ice": "Ice", "wind": "Wind", "thunder": "Lightning", "physical": "Physical", "quantum": "Quantum", "imaginary": "Imaginary"},
    "zh": {"fire": "\u706b", "ice": "\u51b0", "wind": "\u98ce", "thunder": "\u96f7", "physical": "\u7269\u7406", "quantum": "\u91cf\u5b50", "imaginary": "\u865a\u6570"},
    "ja": {"fire": "\u708e", "ice": "\u6c37", "wind": "\u98a8", "thunder": "\u96f7", "physical": "\u7269\u7406", "quantum": "\u91cf\u5b50", "imaginary": "\u865a\u6570"},
    "ko": {"fire": "\ud654\uc5fc", "ice": "\uc5bc\uc74c", "wind": "\ubc14\ub78c", "thunder": "\ubc88\uac1c", "physical": "\ubb3c\ub9ac", "quantum": "\uc591\uc790", "imaginary": "\ud5c8\uc218"},
}

PATH_LABELS = {
    "en": {"warlock": "Nihility", "knight": "Preservation", "rogue": "The Hunt", "mage": "Erudition", "shaman": "Abundance", "warrior": "Destruction", "memory": "Remembrance", "elation": "Elation"},
    "zh": {"warlock": "\u865a\u65e0", "knight": "\u5b58\u62a4", "rogue": "\u5de1\u730e", "mage": "\u667a\u8bc6", "shaman": "\u4e30\u9976", "warrior": "\u6bc1\u706d", "memory": "\u8bb0\u5fc6", "elation": "\u6b22\u6109"},
    "ja": {"warlock": "\u865a\u7121", "knight": "\u5b58\u8b77", "rogue": "\u5de1\u72e9", "mage": "\u77e5\u6075", "shaman": "\u8c4a\u7a63", "warrior": "\u58ca\u6ec5", "memory": "\u8a18\u61b6", "elation": "\u6b53\u559c"},
    "ko": {"warlock": "\ud5c8\ubb34", "knight": "\ubcf4\uc874", "rogue": "\uc218\ub834", "mage": "\uc9c0\uc2dd", "shaman": "\ud48d\uc694", "warrior": "\ud30c\uba78", "memory": "\uae30\uc5b5", "elation": "\ud658\ub77d"},
}

UI_LABELS = {
    "en": {
        "character_card": "CHARACTER CARD", "materials": "MATERIALS",
        "base_stats": "BASE STATS", "stat_bonus": "STAT BONUS", "max_level": "MAX LEVEL 80",
        "hp": "HP", "atk": "ATK", "def": "DEF", "spd": "SPD", "crit_rate": "CRIT RATE", "crit_dmg": "CRIT DMG", "aggro": "AGGRO",
        "ascension": "ASCENSION MATERIALS", "level_range": "LV. 1 - 80",
        "skills": "SKILL MATERIALS", "all_skills": "ALL SKILLS TO LV. 10",
        "total_credits": "TOTAL CREDITS", "voice": "VOICE CAST",
        "base_stats": "BASE STATS", "max_level_short": "MAX LV. 80",
        "base_hp": "Base HP", "base_atk": "Base ATK", "base_def": "Base DEF", "base_spd": "Base SPD",
        "taunt": "Taunt", "max_energy": "Max Energy", "trace_stat_bonus": "TRACE STAT BONUS",
        "voice_cast": "VOICE CAST", "not_credited": "Not credited",
    },
    "zh": {
        "character_card": "\u89d2\u8272\u5361\u7247", "materials": "\u6750\u6599",
        "base_stats": "\u57fa\u7840\u5c5e\u6027", "stat_bonus": "\u5c5e\u6027\u52a0\u6210", "max_level": "\u6ee1\u7ea7 80",
        "hp": "\u751f\u547d\u503c", "atk": "\u653b\u51fb\u529b", "def": "\u9632\u5fa1\u529b", "spd": "\u901f\u5ea6", "crit_rate": "\u66b4\u51fb\u7387", "crit_dmg": "\u66b4\u51fb\u4f24\u5bb3", "aggro": "\u5632\u8bbd\u503c",
        "ascension": "\u664b\u9636\u6750\u6599", "level_range": "Lv. 1-80",
        "skills": "\u884c\u8ff9\u6750\u6599", "all_skills": "\u5168\u90e8\u884c\u8ff9 Lv.10",
        "total_credits": "\u4fe1\u7528\u70b9\u603b\u8ba1", "voice": "\u58f0\u4f18",
        "base_stats": "\u57fa\u7840\u5c5e\u6027", "max_level_short": "\u6ee1\u7ea7 80",
        "base_hp": "\u57fa\u7840\u751f\u547d\u503c", "base_atk": "\u57fa\u7840\u653b\u51fb\u529b", "base_def": "\u57fa\u7840\u9632\u5fa1\u529b", "base_spd": "\u57fa\u7840\u901f\u5ea6",
        "taunt": "\u5632\u8bbd\u503c", "max_energy": "\u6700\u5927\u80fd\u91cf", "trace_stat_bonus": "\u884c\u8ff9\u5c5e\u6027\u52a0\u6210",
        "voice_cast": "\u58f0\u4f18", "not_credited": "\u6682\u65e0\u8bb0\u5f55",
    },
    "ja": {
        "character_card": "\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u30ab\u30fc\u30c9", "materials": "\u7d20\u6750",
        "base_stats": "\u57fa\u672c\u30b9\u30c6\u30fc\u30bf\u30b9", "stat_bonus": "\u30b9\u30c6\u30fc\u30bf\u30b9\u30dc\u30fc\u30ca\u30b9", "max_level": "\u6700\u5927Lv.80",
        "hp": "HP", "atk": "\u653b\u6483\u529b", "def": "\u9632\u5fa1\u529b", "spd": "\u901f\u5ea6", "crit_rate": "\u4f1a\u5fc3\u7387", "crit_dmg": "\u4f1a\u5fc3\u30c0\u30e1\u30fc\u30b8", "aggro": "AGGRO",
        "ascension": "\u6607\u683c\u7d20\u6750", "level_range": "Lv. 1-80",
        "skills": "\u8ecc\u8de1\u7d20\u6750", "all_skills": "\u5168\u8ecc\u8de1 Lv.10",
        "total_credits": "\u5fc5\u8981\u30af\u30ec\u30b8\u30c3\u30c8", "voice": "\u58f0\u512a",
        "base_stats": "\u57fa\u672c\u30b9\u30c6\u30fc\u30bf\u30b9", "max_level_short": "\u6700\u5927Lv.80",
        "base_hp": "\u57fa\u790eHP", "base_atk": "\u57fa\u790e\u653b\u6483\u529b", "base_def": "\u57fa\u790e\u9632\u5fa1\u529b", "base_spd": "\u57fa\u790e\u901f\u5ea6",
        "taunt": "\u6311\u767a\u5024", "max_energy": "\u6700\u5927EP", "trace_stat_bonus": "\u8ecc\u8de1\u30dc\u30fc\u30ca\u30b9",
        "voice_cast": "\u58f0\u512a", "not_credited": "\u672a\u767b\u9332",
    },
    "ko": {
        "character_card": "\uce90\ub9ad\ud130 \uce74\ub4dc", "materials": "\uc7ac\ub8cc",
        "base_stats": "\uae30\ubcf8 \ub2a5\ub825\uce58", "stat_bonus": "\ub2a5\ub825\uce58 \ubcf4\ub108\uc2a4", "max_level": "\ucd5c\ub300 Lv.80",
        "hp": "HP", "atk": "\uacf5\uaca9\ub825", "def": "\ubc29\uc5b4\ub825", "spd": "\uc18d\ub3c4", "crit_rate": "\uce58\uba85\ud0c0 \ud655\ub960", "crit_dmg": "\uce58\uba85\ud0c0 \ud53c\ud574", "aggro": "AGGRO",
        "ascension": "\uc2b9\uae09 \uc7ac\ub8cc", "level_range": "Lv. 1-80",
        "skills": "\uada4\uc801 \uc7ac\ub8cc", "all_skills": "\ubaa8\ub4e0 \uc2a4\ud0ac Lv.10",
        "total_credits": "\ucd1d \ud06c\ub808\ub527", "voice": "\uc131\uc6b0",
        "base_stats": "\uae30\ubcf8 \ub2a5\ub825\uce58", "max_level_short": "\ucd5c\ub300 Lv.80",
        "base_hp": "\uae30\ubcf8 HP", "base_atk": "\uae30\ubcf8 \uacf5\uaca9\ub825", "base_def": "\uae30\ubcf8 \ubc29\uc5b4\ub825", "base_spd": "\uae30\ubcf8 \uc18d\ub3c4",
        "taunt": "\ub3c4\ubc1c \uc218\uce58", "max_energy": "\ucd5c\ub300 \uc5d0\ub108\uc9c0", "trace_stat_bonus": "\ud589\uc801 \ub2a5\ub825\uce58 \ubcf4\ub108\uc2a4",
        "voice_cast": "\uc131\uc6b0", "not_credited": "\ubbf8\ub4f1\ub85d",
    },
}


def ui(data: CardData, key: str) -> str:
    return UI_LABELS.get(data.locale, UI_LABELS["en"]).get(key, UI_LABELS["en"].get(key, key))


def wrap_text(draw, text, fnt, width, locale="en"):
    if locale not in ("zh", "ja"):
        return wrap(draw, text, fnt, width)
    lines = []
    paragraphs = str(text).replace("\\n", "\n").split("\n")
    for paragraph in paragraphs:
        line = ""
        for char in paragraph:
            candidate = line + char
            if not line or draw.textlength(candidate, font=fnt) <= width:
                line = candidate
            else:
                lines.append(line)
                line = char
        if line:
            lines.append(line)
    return lines


DETAIL_PUNCT = re.compile(r"^[,.;:!?%\u2026\)\]\}\u2019\u201d]+$")


@dataclass
class DetailPiece:
    text: str
    color: tuple[int, int, int, int]
    strike: bool = False


def _detail_units(text: str, locale: str) -> list[tuple[str, bool]]:
    """Split rich diff text into drawable words, keeping punctuation glued."""
    if not text:
        return []
    if locale in ("zh", "ja"):
        pattern = re.compile(r"\s+|[\u4e00-\u9fff\u3040-\u30ff]|[^\s\u4e00-\u9fff\u3040-\u30ff]+")
    else:
        pattern = re.compile(r"\s+|[^\s]+")
    units: list[tuple[str, bool]] = []
    pending_space = False
    for token in pattern.findall(text):
        if token.isspace():
            pending_space = True
            continue
        if units and DETAIL_PUNCT.fullmatch(token):
            units[-1] = (units[-1][0] + token, units[-1][1])
            continue
        units.append((token, pending_space))
        pending_space = False
    return units


def layout_detail_lines(draw, runs, fnt, width: int, locale: str) -> list[list[DetailPiece]]:
    """Word-wrap ``(text, kind, color)`` runs for the identity description."""
    lines: list[list[DetailPiece]] = [[]]
    line_w = 0.0
    space_w = draw.textlength(" ", font=fnt)

    def add(text: str, color, strike: bool, space_before: bool) -> None:
        nonlocal line_w
        if not text:
            return
        if text == "\n":
            lines.append([])
            line_w = 0.0
            return
        piece_w = draw.textlength(text, font=fnt)
        gap = space_w if space_before and lines[-1] else 0.0
        if lines[-1] and line_w + gap + piece_w > width + 0.5:
            lines.append([])
            line_w = 0.0
            gap = 0.0
        if gap:
            lines[-1].append(DetailPiece(" ", color))
            line_w += gap
        lines[-1].append(DetailPiece(text, color, strike))
        line_w += piece_w

    for text, kind, color in runs:
        for chunk in re.split(r"(\n)", text):
            if chunk == "\n":
                add("\n", color, False, False)
                continue
            for unit, space_before in _detail_units(chunk, locale):
                add(unit, color, kind == "removed", space_before or bool(lines[-1]))
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def draw_detail_lines(draw, lines, x: int, y: int, fnt, line_h: int, locale: str) -> int:
    """Draw wrapped identity lines, adding strikethroughs to removed words."""
    for index, line in enumerate(lines):
        cursor = float(x)
        baseline = y + index * line_h
        for piece in line:
            draw.text((cursor, baseline), piece.text, font=fnt, fill=piece.color)
            piece_w = draw.textlength(piece.text, font=fnt)
            if piece.strike and piece.text.strip():
                strike_y = baseline + round(fnt.size * 0.62)
                draw.line((cursor, strike_y, cursor + piece_w, strike_y), fill=piece.color, width=max(1, fnt.size // 13))
            cursor += piece_w
    return len(lines) * line_h


@dataclass
class CardData:
    character_id: int
    locale: str
    version: str
    name: str
    desc: str
    stars: int
    detail: Any
    items: dict[str, Any]
    stats: dict[str, float]
    bonuses: list[tuple[str, float, str]]
    sp_need: int | None
    icon_dir: Path | None
    ascension: list[Any]
    skills: list[Any]
    icons: dict[int, Path | None]
    splash: Image.Image | None
    element_icon: Image.Image | None
    path_icon: Image.Image | None
    element_label: str
    path_label: str
    before: "CardData | None" = None

    @property
    def comparison(self) -> bool:
        return self.before is not None


def heavy(size: int, locale: str = "en", display: bool = False):
    if display and locale == "en":
        return font(size, display=True)
    return font(size, bold=True, locale=locale)

def text_locale(text: str, default: str = "en") -> str:
    """Pick a font locale for names that can contain CJK or Hangul."""
    if not text:
        return default
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return default


def base_canvas(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), BG)
    img.alpha_composite(radial((1100, 900), (116, 68, 205), 0.30), (-330, -460))
    img.alpha_composite(radial((800, 800), (217, 87, 57), 0.16), (700, -300))
    return img


def heading(draw, x, y, title, subtitle, width, locale="en", size=24):
    draw.rectangle((x, y + 8, x + 26, y + 12), fill=PURPLE)
    draw.text((x + 38, y - 5), title, font=heavy(size, locale), fill=PURPLE)
    if subtitle:
        sub = font(17, bold=True, locale=locale)
        sw = draw.textlength(subtitle, font=sub)
        draw.text((x + width - sw, y), subtitle, font=sub, fill=DIM)
    draw.line((x, y + 42, x + width - 2, y + 42), fill=LINE, width=1)


def fit(draw, text, fnt, width):
    text = str(text)
    if draw.textlength(text, font=fnt) <= width:
        return text
    suffix = "..."
    while text and draw.textlength(text + suffix, font=fnt) > width:
        text = text[:-1]
    return text.rstrip() + suffix


def tag(canvas, draw, x, y, label, color, locale="en", size=19, height=42):
    fnt = heavy(size, locale)
    width = draw.textlength(label, font=fnt) + 44
    layer = Image.new("RGBA", (round(width), height), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((0, 0, width - 1, height - 1), radius=height // 2, fill=(*color[:3], 38), outline=(*color[:3], 145), width=1)
    canvas.alpha_composite(layer, (round(x), round(y)))
    draw.text((x + 22, y + 8), label, font=fnt, fill=color)
    return width


def variation_text(data: CardData) -> str:
    if data.before is not None:
        return f"v{data.before.version} \u2192 v{data.version}  /  {data.locale.upper()}"
    return f"v{data.version}  /  {data.locale.upper()}"


def version_pill(canvas, draw, data: CardData, width: int, y=26):
    vtext = variation_text(data)
    vf = heavy(17, data.locale)
    vw = draw.textlength(vtext, font=vf)
    x0 = width - M - vw - 36
    composite_panel(canvas, (x0, y, width - M, y + 46), 23, (19, 13, 33, 248), (255, 255, 255, 70))
    draw.text((x0 + 18, y + 10), vtext, font=vf, fill=TEXT)


def splash(canvas, data: CardData, target_h: int, x: int, y: int):
    if not data.splash:
        return
    img = data.splash
    scale = target_h / img.height
    img = img.resize((round(img.width * scale), target_h), Image.Resampling.LANCZOS)
    glow = radial((800, 800), (246, 172, 87), 0.18)
    canvas.alpha_composite(glow, (x - 90, y + 80))
    canvas.alpha_composite(img, (x, y))


def identity(canvas, draw, data: CardData, x: int, y: int, title_size: int, desc_width: int, desc_lines: int):
    title_font = heavy(title_size, data.locale, display=True)
    title = data.name.upper() if data.locale == "en" else data.name
    lines = wrap(draw, title, title_font, 760)[:2]
    for line in lines:
        draw.text((x, y), line, font=title_font, fill=TEXT, stroke_width=1 if data.locale == "en" else 0, stroke_fill=TEXT)
        y += round(title_size * 1.02)
    if data.before is not None and data.before.name != data.name:
        old_name = data.before.name.upper() if data.locale == "en" else data.before.name
        old_font = font(15, locale=data.locale)
        old_w = draw.textlength(old_name, font=old_font)
        draw.text((x, y - 2), old_name, font=old_font, fill=(224, 150, 164, 255))
        strike_y = y + 7
        draw.line((x, strike_y, x + old_w, strike_y), fill=(224, 150, 164, 255), width=1)
        y += 26
    y += 10
    for i in range(data.stars or 5):
        make_star(canvas, x + 16 + i * 34, y + 16, 14, GOLD)
    y += 54
    tag_x = x
    for label, color, icon in ((data.element_label.upper(), FIRE, data.element_icon), (data.path_label.upper(), PURPLE, data.path_icon)):
        if icon:
            canvas.alpha_composite(icon.resize((32, 32), Image.Resampling.LANCZOS), (round(tag_x), round(y + 5)))
            w = tag(canvas, draw, round(tag_x) + 42, round(y), label, color, data.locale, 18, 42)
            tag_x = round(tag_x + w + 58)
        else:
            w = tag(canvas, draw, round(tag_x), round(y), label, color, data.locale, 18, 42)
            tag_x = round(tag_x + w + 18)
    y += 62
    if desc_lines and data.desc:
        desc_font = font(22, locale=data.locale)
        if data.before is not None:
            runs = diff_words(data.before.desc, data.desc, data.locale)
            colors = {
                "removed": (224, 150, 164, 255),
                "added": (142, 216, 168, 255),
                "arrow": (150, 138, 175, 255),
                "equal": MUTED,
            }
            rich = [(text, kind, colors.get(kind, MUTED)) for text, kind in runs]
            lines = layout_detail_lines(draw, rich, desc_font, desc_width, data.locale)[:desc_lines]
            draw_detail_lines(draw, lines, x, y, desc_font, 31, data.locale)
        else:
            lines = wrap_text(draw, data.desc, desc_font, desc_width, data.locale)
            for index, line in enumerate(lines[:desc_lines]):
                suffix = "..." if index == desc_lines - 1 and len(lines) > desc_lines else ""
                draw.text((x, y), line + suffix, font=desc_font, fill=MUTED)
                y += 31


REMOVED_COLOR = (224, 150, 164, 255)
ADDED_COLOR = (142, 216, 168, 255)
ARROW_COLOR = (150, 138, 175, 255)


def _strike(draw, x: float, y: float, width: float, color, size: int = 16) -> None:
    draw.line((x, y, x + width, y), fill=color, width=max(1, size // 12))


def change_overlay(canvas, box, *, radius: int = 12) -> None:
    """Tint one changed comparison block without hiding its contents."""
    x0, y0, x1, y1 = (round(value) for value in box)
    layer = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(
        (0, 0, layer.width - 1, layer.height - 1),
        radius=radius,
        fill=(142, 216, 168, 22),
        outline=(142, 216, 168, 52),
        width=1,
    )
    canvas.alpha_composite(layer, (x0, y0))


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
    """Show changed/added material rows first, then unchanged rows to fill the grid."""
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
    draw.text((x, y), ui(data, "total_credits"), font=font(14, bold=True, locale=data.locale), fill=DIM)
    _credits_value(draw, x, y, width, amount, before_amount, data.locale)
    icon = load_webp(data.icons.get(2), (42, 42))
    if icon:
        canvas.alpha_composite(icon, (x + width - 46, y + 16))
    draw.line((x, y + 70, x + width, y + 70), fill=LINE, width=1)


def material_item(canvas, draw, data: CardData, x, y, width, cost, icon_size, name_size, stacked=False, before_amount=None, added=False, removed=False):
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
    """Union material rows: new list first, then removed materials."""
    old = {cost.item_id: cost.amount for cost in before}
    new = {cost.item_id: cost.amount for cost in after}
    rows = []
    for cost in after:
        rows.append((cost, old.get(cost.item_id), cost.item_id not in old, False))
    for cost in before:
        if cost.item_id not in new:
            rows.append((cost, cost.amount, False, True))
    return rows


BONUS_ICONS = {
    "HP": "IconMaxHP.webp",
    "ATK": "IconAttack.webp",
    "DEF": "IconDefence.webp",
    "SPD": "IconSpeed.webp",
    "CRIT Rate": "IconCriticalChance.webp",
    "CRIT DMG": "IconCriticalDamage.webp",
    "Fire DMG Boost": "IconFireAddedRatio.webp",
    "Ice DMG Boost": "IconIceAddedRatio.webp",
    "Wind DMG Boost": "IconWindAddedRatio.webp",
    "Lightning DMG Boost": "IconThunderAddedRatio.webp",
    "Physical DMG Boost": "IconPhysicalAddedRatio.webp",
    "Quantum DMG Boost": "IconQuantumAddedRatio.webp",
    "Imaginary DMG Boost": "IconImaginaryAddedRatio.webp",
}

BASIC_STAT_ICONS = {
    "hp": "IconMaxHP.webp",
    "atk": "IconAttack.webp",
    "def": "IconDefence.webp",
    "spd": "IconSpeed.webp",
}


def stat_icon(data: CardData, name: str, size: int = 24):
    path = data.icon_dir / name if data.icon_dir else None
    return load_webp(path, (size, size))


def bonus_icon_name(label: str) -> str | None:
    return BONUS_ICONS.get(label)


def stat_row(canvas, draw, data: CardData, x, y, width, label, value, icon_name=None, value_size=22, icon_size=24, before_value=None):
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

def ascension_panel(canvas, draw, data: CardData, y: int, height: int, icon_size: int, name_size: int):
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

def footer(draw, width, height, data: CardData):
    draw.line((M, height - 44, width - M, height - 44), fill=LINE, width=1)
    if data.before is not None:
        label = f"NANOKA HSR  /  DATA v{data.before.version} \u2192 v{data.version}  /  {data.locale.upper()}"
    else:
        label = f"NANOKA HSR  /  DATA v{data.version}  /  {data.locale.upper()}"
    draw.text((M, height - 30), label, font=heavy(13, data.locale), fill=DIM)


def render_hero(data: CardData) -> Image.Image:
    width, height = 1080, 1250
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 640), fill=(12, 8, 23, 255))
    draw.line((M, 74, width - M, 74), fill=LINE, width=1)
    draw.text((M, 32), f"NANOKA / HSR  /  {ui(data, 'character_card')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 570, 576, 48)
    version_pill(canvas, draw, data, width, 26)
    identity(canvas, draw, data, M, 108, 78, 560, 2)
    draw_compact_stats_panel(canvas, draw, data, 650)
    ascension_panel(canvas, draw, data, 918, 232, 60, 21)
    footer(draw, width, height, data)
    return canvas


def render_materials(data: CardData) -> Image.Image:
    width, height = 1080, 1250
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 390), fill=(12, 8, 23, 255))
    draw.line((M, 72, width - M, 72), fill=LINE, width=1)
    draw.text((M, 30), f"NANOKA / HSR  /  {ui(data, 'materials')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 350, 674, 42)
    version_pill(canvas, draw, data, width, 24)
    identity(canvas, draw, data, M, 100, 62, 590, 2)
    ascension_panel(canvas, draw, data, 414, 250, 62, 21)
    skills_panel(canvas, draw, data, 738, 412, 56, 21)
    footer(draw, width, height, data)
    return canvas


def render_detail(data: CardData, with_voice: bool = False) -> Image.Image:
    if data.before is not None:
        return render_detail_comparison(data)
    width, height = 1080, 1440
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 430), fill=(12, 8, 23, 255))
    draw.line((M, 72, width - M, 72), fill=LINE, width=1)
    draw.text((M, 30), f"NANOKA / HSR  /  {ui(data, 'character_card')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 400, 650, 50)
    version_pill(canvas, draw, data, width, 24)
    identity(canvas, draw, data, M, 102, 66, 570, 3)
    draw_stats_panel(canvas, draw, data, 424, compact=False)
    ascension_panel(canvas, draw, data, 758, 220, 60, 21)
    skills_panel(canvas, draw, data, 1050, 286, 46, 19, row_h=42)
    footer(draw, width, height, data)
    return canvas


def comparison_rows(costs, before_costs, limit=None):
    rows = compare_costs(before_costs, costs)
    return rows[:limit] if limit is not None else rows


def render_detail_comparison(data: CardData) -> Image.Image:
    """Comparison info card: same composition, with changed values inline."""
    asc_rows = compact_rows([row for row in comparison_rows(data.ascension, data.before.ascension) if row[0].item_id != 2], 4)
    skill_rows = compact_rows([row for row in comparison_rows(data.skills, data.before.skills) if row[0].item_id != 2], 8)
    asc_h = 220 + max(0, (len(asc_rows) + 1) // 2 - 2) * 72
    skill_row_h = 42
    skill_h = 286 + max(0, (len(skill_rows) + 1) // 2 - 4) * skill_row_h
    asc_y = 758
    skill_y = asc_y + 48 + asc_h + 24
    height = max(1440, skill_y + skill_h + 70)
    width = 1080
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 430), fill=(12, 8, 23, 255))
    draw.line((M, 72, width - M, 72), fill=LINE, width=1)
    draw.text((M, 30), f"NANOKA / HSR  /  {ui(data, 'character_card')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 400, 650, 50)
    version_pill(canvas, draw, data, width, 24)
    identity(canvas, draw, data, M, 102, 66, 570, 3)
    draw_stats_panel(canvas, draw, data, 424, compact=False)
    ascension_panel(canvas, draw, data, asc_y, asc_h, 60, 21)
    skills_panel(canvas, draw, data, skill_y, skill_h, 46, 19, row_h=skill_row_h)
    footer(draw, width, height, data)
    return canvas

async def load_data(
    character_id: int | str,
    locale: str,
    *,
    version: str | None = None,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[CardData, CharacterData]:
    character = await load_character(
        character_id,
        version=version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
    )
    try:
        return await build_card_data(character), character
    except BaseException:
        await character.client.close()
        raise


async def build_card_data(character: CharacterData) -> CardData:
    detail = character.detail
    locale = character.locale
    character_id = character.character_id
    icons: dict[int, Path | None] = {}
    relatives = [f"itemfigures/2.webp"]
    for stat in detail.stats.values():
        for cost in stat.cost:
            relatives.append(f"itemfigures/{cost.item_id}.webp")
    for trace in detail.traces:
        for level in trace.levels:
            for cost in level.material_list:
                relatives.append(f"itemfigures/{cost.item_id}.webp")
    relatives.extend(
        [
            f"avatardrawcard/{character_id}.webp",
            f"element/{character.element}.webp",
            f"pathicon/{character.path}.webp",
        ]
    )
    await prime_assets(character, relatives)
    asset_root = character.client.cache.asset_file("")
    for stat in detail.stats.values():
        for cost in stat.cost:
            icons[cost.item_id] = asset_root / "itemfigures" / f"{cost.item_id}.webp"
    for trace in detail.traces:
        for level in trace.levels:
            for cost in level.material_list:
                icons[cost.item_id] = icons.get(cost.item_id) or asset_root / "itemfigures" / f"{cost.item_id}.webp"

    asset_root = character.client.cache.asset_file("")
    for item_id, path in icons.items():
        if path is None or not path.is_file():
            fallback = asset_root / "itemfigures" / f"{item_id}.webp"
            icons[item_id] = fallback if fallback.is_file() else None

    element = character.element
    path_code = character.path
    data = CardData(
        character_id=character_id,
        locale=locale,
        version=character.version,
        name=clean_localized(character.name, locale) or str(character_id),
        desc=clean_localized(character.description, locale),
        stars=character.stars,
        detail=detail,
        items=character.items,
        stats=max_stats(detail),
        bonuses=bonus_stats(detail, locale),
        sp_need=detail.sp_need,
        icon_dir=asset_root / "skillicons",
        ascension=aggregate([cost for stat in detail.stats.values() for cost in stat.cost]),
        skills=skill_materials(detail),
        icons=icons,
        splash=load_webp(asset_root / "avatardrawcard" / f"{character_id}.webp"),
        element_icon=load_webp(asset_root / "element" / f"{element}.webp"),
        path_icon=load_webp(asset_root / "pathicon" / f"{path_code}.webp"),
        element_label=ELEMENT_LABELS.get(locale, ELEMENT_LABELS["en"]).get(element, element.title()),
        path_label=PATH_LABELS.get(locale, PATH_LABELS["en"]).get(path_code, (detail.path or "").title()),
    )
    return data


async def build_comparison_card_data(
    identifier: int | str,
    from_version: str,
    to_version: str,
    locale: str = "en",
    *,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[CardData, CharacterData, CharacterData]:
    """Load one character at two versions and return the newer comparison model."""
    before_character = await load_character(
        identifier, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy
    )
    try:
        after_character = await load_character(
            identifier, version=to_version, locale=locale, cache_dir=cache_dir, proxy=proxy
        )
    except BaseException:
        await before_character.client.close()
        raise
    try:
        before = await build_card_data(before_character)
        after = await build_card_data(after_character)
    except BaseException:
        await before_character.client.close()
        await after_character.client.close()
        raise
    after.before = before
    after.icons = {**before.icons, **after.icons}
    return after, before_character, after_character

async def build_all(character_id: int, locale: str, output_dir: Path, with_voice: bool = False):
    data, character = await load_data(character_id, locale)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if locale == "en" else f"_{locale}"
    variants = {
        f"character_{character_id}_hero_1080x1250{suffix}.png": render_hero(data),
        f"character_{character_id}_materials_1080x1250{suffix}.png": render_materials(data),
        f"character_{character_id}_detail_1080x1440{suffix}.png": render_detail(data, with_voice=with_voice),
    }
    for name, image in variants.items():
        path = output_dir / name
        image.convert("RGB").save(path, quality=95, subsampling=0)
        print(f"{path} ({path.stat().st_size:,} bytes)")
    await character.client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("character_id", type=int)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--with-voice", action="store_true", help="Accepted for compatibility; voice cast is always in the detail panel")
    args = parser.parse_args()
    asyncio.run(build_all(args.character_id, args.locale, args.out))


if __name__ == "__main__":
    main()
