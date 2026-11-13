from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ...nanoka import NanokaClient

W, H = 2400, 1540
M = 96
BG = (9, 6, 18, 255)
TEXT = (245, 241, 255, 255)
MUTED = (167, 154, 190, 255)
DIM = (112, 99, 139, 255)
PURPLE = (190, 151, 255, 255)
GOLD = (244, 201, 107, 255)
FIRE = (242, 138, 104, 255)
GREEN = (142, 216, 168, 255)
LINE = (255, 255, 255, 25)
PANEL_FILL = (25, 20, 38, 220)
PANEL_EDGE = (255, 255, 255, 30)

FONT_DIR = Path("C:/Windows/Fonts")
FONT_REG = FONT_DIR / "segoeui.ttf"
FONT_BOLD = FONT_DIR / "segoeuib.ttf"
FONT_SEMI = FONT_DIR / "segoeuisl.ttf"
FONT_DISPLAY = FONT_DIR / "bahnschrift.ttf"

LOCALE_FONTS = {
    "zh": FONT_DIR / "msyh.ttc",
    "ja": FONT_DIR / "YuGothM.ttc",
    "ko": FONT_DIR / "malgun.ttf",
}

LOCALE_BOLD_FONTS = {
    "zh": FONT_DIR / "msyhbd.ttc",
    "ja": FONT_DIR / "YuGothB.ttc",
    "ko": FONT_DIR / "malgunbd.ttf",
}

ELEMENT_NAMES = {
    "physical": "Physical",
    "fire": "Fire",
    "ice": "Ice",
    "thunder": "Lightning",
    "wind": "Wind",
    "quantum": "Quantum",
    "imaginary": "Imaginary",
}

PATH_NAMES = {
    "warlock": "Nihility",
    "knight": "Preservation",
    "rogue": "The Hunt",
    "mage": "Erudition",
    "shaman": "Abundance",
    "warrior": "Destruction",
    "memory": "Remembrance",
    "elation": "Elation",
}

MATERIAL_SECTIONS = (
    ("ASCENSION MATERIALS", "LV. 1 - 80", ("point",)),
    ("SKILL MATERIALS", "ALL SKILLS TO LV. 10", ("point02", "point04")),
    ("TRACE MATERIALS", "BONUS ABILITIES", ("point06", "point07", "point08")),
)


def font(size: int, *, bold: bool = False, display: bool = False, locale: str = "en"):
    if display and locale == "en":
        path = FONT_DISPLAY
    elif bold:
        path = FONT_BOLD
    else:
        path = FONT_REG
    if locale in LOCALE_FONTS:
        candidates = (LOCALE_BOLD_FONTS.get(locale), LOCALE_FONTS[locale]) if bold or display else (LOCALE_FONTS[locale],)
        for candidate in candidates:
            if candidate and candidate.exists():
                path = candidate
                break
    if not path.exists():
        path = FONT_REG
    return ImageFont.truetype(str(path), size)


def gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(4))
        draw.line((0, y, w, y), fill=color)
    return img


def radial(size, color, opacity=1.0):
    w, h = size
    small = (max(2, w // 8), max(2, h // 8))
    img = Image.new("RGBA", small, (*color[:3], 0))
    draw = ImageDraw.Draw(img)
    radius = min(small) / 2
    for i in range(int(radius), 0, -1):
        alpha = round(255 * opacity * (1 - i / radius) ** 1.7)
        draw.ellipse(
            (small[0] // 2 - i, small[1] // 2 - i, small[0] // 2 + i, small[1] // 2 + i),
            fill=(*color[:3], alpha),
        )
    return img.resize((w, h), Image.Resampling.LANCZOS)


def soft_panel(size, radius, fill=PANEL_FILL, edge=PANEL_EDGE, width=1):
    w, h = max(1, round(size[0])), max(1, round(size[1]))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill, outline=edge, width=width)
    return layer


def composite_panel(canvas, box, radius, fill=PANEL_FILL, edge=PANEL_EDGE, width=1):
    x0, y0, x1, y1 = (round(value) for value in box)
    canvas.alpha_composite(soft_panel((x1 - x0, y1 - y0), radius, fill, edge, width), (x0, y0))


def rounded_tag(canvas, draw, xy, label, color, text_color=None, fill_alpha=38, border_alpha=120):
    x, y = xy
    fnt = font(19, bold=True)
    tw = draw.textlength(label, font=fnt)
    h = 42
    w = tw + 48
    layer = Image.new("RGBA", (int(w), h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle(
        (0, 0, w - 1, h - 1),
        radius=h // 2,
        fill=(*color[:3], fill_alpha),
        outline=(*color[:3], border_alpha),
        width=1,
    )
    canvas.alpha_composite(layer, (int(x), int(y)))
    draw.text((x + 24, y + 9), label, font=fnt, fill=text_color or color)
    return w


def wrap(draw, text, fnt, max_width):
    if not text:
        return []
    paragraphs = text.replace("\\n", "\n").split("\n")
    lines = []
    for paragraph in paragraphs:
        words = paragraph.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if draw.textlength(candidate, font=fnt) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def load_webp(path, size=None):
    if not path or not path.exists():
        return None
    image = Image.open(path).convert("RGBA")
    if size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def asset(client, folder, key, suffix="webp"):
    path = client.cache_path / "assets" / folder / f"{key}.{suffix}"
    return path if path.exists() else None


def make_star(canvas, cx, cy, radius, color):
    points = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = radius if i % 2 == 0 else radius * 0.43
        points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    ImageDraw.Draw(canvas).polygon(points, fill=color)


@dataclass
class Cost:
    item_id: int
    amount: int


def aggregate(costs):
    totals = {}
    for cost in costs:
        amount = getattr(cost, "item_num", None)
        if amount is None:
            amount = getattr(cost, "amount", 0)
        totals[cost.item_id] = totals.get(cost.item_id, 0) + int(amount or 0)
    return [Cost(item_id=item_id, amount=amount) for item_id, amount in totals.items()]


# Skill-tree point types published by Nanoka:
#   1 = minor trace, 2 = combat skill, 3 = bonus ability,
#   4 = extra skill track (Memosprite / Elation / Trailblazer),
#   5 = special passive, 6 = special authority.
SKILL_MATERIAL_POINT_TYPES = (2, 4)


def skill_material_costs(detail):
    """Return trace rows for every directly levelled combat/extra skill.

    Point ids are not stable across characters: ``point01``-``point04`` misses
    the Elation/Memosprite/Trailblazer tracks, which are separate point types
    4. Selecting by ``point_type`` keeps all published kits correct.
    """
    return [
        cost
        for levels in detail.skill_trees.values()
        for level in levels.values()
        if level.point_type in SKILL_MATERIAL_POINT_TYPES
        for cost in level.material_list
    ]


def skill_materials(detail):
    return aggregate(skill_material_costs(detail))


def max_stats(detail):
    key = max(detail.stats, key=lambda value: int(value) if str(value).isdigit() else -1)
    raw = detail.stats[key]
    level = int(key) if str(key).isdigit() else 80
    # Nanoka stores base stats at level 1 and the per-level growth separately.
    # The level bucket is the ascension cap (e.g. 6 = level 80), so calculate 80 explicitly.
    growth = max(0, 80 - 1) if level >= 6 else max(0, level - 1)
    return {
        "hp": (raw.hp_base or 0) + (raw.hp_add or 0) * growth,
        "atk": (raw.attack_base or 0) + (raw.attack_add or 0) * growth,
        "def": (raw.defence_base or 0) + (raw.defence_add or 0) * growth,
        "spd": raw.speed_base or 0,
        "crit": (raw.critical_chance or 0) * 100,
        "crit_dmg": (raw.critical_damage or 0) * 100,
        "aggro": raw.base_aggro or 0,
    }


BONUS_LABELS = {
    "HPAddedRatio": {"en": "HP", "zh": "Ã§â€Å¸Ã¥â€˜Â½Ã¥â‚¬Â¼", "ja": "HP", "ko": "HP"},
    "AttackAddedRatio": {"en": "ATK", "zh": "Ã¦â€Â»Ã¥â€¡Â»Ã¥Å â€º", "ja": "Ã¦â€Â»Ã¦â€™Æ’Ã¥Å â€º", "ko": "ÃªÂ³ÂµÃªÂ²Â©Ã«Â Â¥"},
    "DefenceAddedRatio": {"en": "DEF", "zh": "Ã©ËœÂ²Ã¥Â¾Â¡Ã¥Å â€º", "ja": "Ã©ËœÂ²Ã¥Â¾Â¡Ã¥Å â€º", "ko": "Ã«Â°Â©Ã¬â€“Â´Ã«Â Â¥"},
    "SpeedAddedRatio": {"en": "SPD", "zh": "Ã©â‚¬Å¸Ã¥ÂºÂ¦", "ja": "Ã©â‚¬Å¸Ã¥ÂºÂ¦", "ko": "Ã©â‚¬Å¸Ã¥ÂºÂ¦"},
    "CriticalChanceBase": {"en": "CRIT Rate", "zh": "Ã¦Å¡Â´Ã¥â€¡Â»Ã§Å½â€¡", "ja": "Ã¤Â¼Å¡Ã¥Â¿Æ’Ã§Å½â€¡", "ko": "Ã¬Â¹ËœÃ«Âªâ€¦Ã­Æ’â‚¬ Ã­â„¢â€¢Ã«Â¥Â "},
    "CriticalDamageBase": {"en": "CRIT DMG", "zh": "Ã¦Å¡Â´Ã¥â€¡Â»Ã¤Â¼Â¤Ã¥Â®Â³", "ja": "Ã¤Â¼Å¡Ã¥Â¿Æ’Ã£Æ’â‚¬Ã£Æ’Â¡Ã£Æ’Â¼Ã£â€šÂ¸", "ko": "Ã¬Â¹ËœÃ«Âªâ€¦Ã­Æ’â‚¬ Ã­â€Â¼Ã­â€¢Â´"},
    "IceAddedRatio": {"en": "Ice DMG Boost"}, "WindAddedRatio": {"en": "Wind DMG Boost"}, "LightningAddedRatio": {"en": "Lightning DMG Boost"}, "PhysicalAddedRatio": {"en": "Physical DMG Boost"}, "QuantumAddedRatio": {"en": "Quantum DMG Boost"}, "ImaginaryAddedRatio": {"en": "Imaginary DMG Boost"}, "FireAddedRatio": {"en": "Fire DMG Boost", "zh": "Ã§ÂÂ«Ã¥Â±Å¾Ã¦â‚¬Â§Ã¤Â¼Â¤Ã¥Â®Â³Ã¦ÂÂÃ©Â«Ëœ", "ja": "Ã§â€šÅ½Ã¥Â±Å¾Ã¦â‚¬Â§Ã£Æ’â‚¬Ã£Æ’Â¡Ã£Æ’Â¼Ã£â€šÂ¸", "ko": "Ã­â„¢â€Ã¬â€”Â¼ Ã¬â€ ÂÃ¬â€žÂ± Ã­â€Â¼Ã­â€¢Â´"},
}


def bonus_stats(detail, locale="en"):
    totals = {}
    for trace in detail.minor_traces:
        for level in trace.levels:
            if not level.status_add_list:
                continue
            for status in level.status_add_list:
                key = status.get("property_type")
                if key:
                    totals[key] = totals.get(key, 0) + float(status.get("value") or 0)
    order = ["HPAddedRatio", "CriticalChanceBase", "FireAddedRatio", "IceAddedRatio", "WindAddedRatio", "LightningAddedRatio", "PhysicalAddedRatio", "QuantumAddedRatio", "ImaginaryAddedRatio", "SpeedAddedRatio", "AttackAddedRatio", "DefenceAddedRatio", "CriticalDamageBase"]
    result = []
    for key in order:
        if key in totals:
            labels = BONUS_LABELS.get(key, {})
            result.append((labels.get(locale) or labels.get("en") or key, totals.pop(key) * 100))
    for key, value in totals.items():
        if value:
            labels = BONUS_LABELS.get(key, {})
            result.append((labels.get(locale) or labels.get("en") or key, value * 100))
    return result or [("No minor traces", 0)]


def clean_localized(text, locale):
    if not text:
        return text
    if locale == "ja" and "{RUBY_" in text:
        import re

        text = re.sub(r"\{RUBY_B#[^}]*\}", "", text)
        text = text.replace("{RUBY_E#}", "")
    return text


WEEKLY_FALLBACK = {
    "en": "Weekly Boss Material",
    "zh": "Ã¥Å½â€ Ã¦Ë†ËœÃ¤Â½â„¢Ã¥â€œÂÃ¦ÂÂÃ¦â€“â„¢",
    "ja": "Ã©â‚¬Â±Ã£Æ’Å“Ã£â€šÂ¹Ã§Â´Â Ã¦ÂÂ",
    "ko": "Ã¬Â£Â¼ÃªÂ°â€ž Ã«Â³Â´Ã¬Å Â¤ Ã¬Å¾Â¬Ã«Â£Å’",
}


def material_name(items, item_id, locale="en"):
    entry = items.get(str(item_id)) or {}
    name = entry.get("item_name")
    if not name or name == "...":
        if entry.get("item_sub_type") == "WeeklyMonsterDrop":
            return WEEKLY_FALLBACK.get(locale, WEEKLY_FALLBACK["en"])
        return f"Material {item_id}"
    return re.sub(r"<[^>]+>", "", str(name)).strip()


def add_corner_marks(canvas, box, color=(255, 255, 255, 38), length=18, inset=0):
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(canvas)
    x0 += inset
    y0 += inset
    x1 -= inset
    y1 -= inset
    segments = [
        ((x0, y0), (x0 + length, y0)),
        ((x0, y0), (x0, y0 + length)),
        ((x1, y0), (x1 - length, y0)),
        ((x1, y0), (x1, y0 + length)),
        ((x0, y1), (x0 + length, y1)),
        ((x0, y1), (x0, y1 - length)),
        ((x1, y1), (x1 - length, y1)),
        ((x1, y1), (x1, y1 - length)),
    ]
    for start, end in segments:
        draw.line((start, end), fill=color, width=2)


def section_title(draw, x, y, title, subtitle, width):
    draw.rectangle((x, y + 7, x + 20, y + 10), fill=PURPLE)
    draw.text((x + 32, y - 5), title, font=font(20, bold=True), fill=PURPLE)
    if subtitle:
        sub_font = font(14, bold=True)
        sw = draw.textlength(subtitle, font=sub_font)
        draw.text((x + width - sw, y), subtitle, font=sub_font, fill=DIM)
    draw.line((x, y + 34, x + width - 4, y + 34), fill=LINE, width=1)


def draw_icon_row(canvas, draw, costs, icons, items, x, y, width, row_gap=64, icon_size=44, name_size=17):
    for index, cost in enumerate(costs):
        row_y = y + index * row_gap
        icon = load_webp(icons.get(cost.item_id), (icon_size, icon_size))
        if icon:
            canvas.alpha_composite(icon, (x, row_y - 4))
        name = material_name(items, cost.item_id)
        name_font = font(name_size, bold=False)
        max_name = width - icon_size - 92
        if draw.textlength(name, font=name_font) > max_name:
            while name and draw.textlength(name + "...", font=name_font) > max_name:
                name = name[:-1]
            name = name.rstrip() + "..."
        draw.text((x + icon_size + 14, row_y + 1), name, font=name_font, fill=TEXT)
        qty = f"x{cost.amount:,}"
        qf = font(name_size + 1, bold=True)
        qx = x + width - draw.textlength(qty, font=qf)
        draw.text((qx, row_y + 1), qty, font=qf, fill=GOLD)
        draw.line((x, row_y + row_gap - 14, x + width, row_y + row_gap - 14), fill=(255, 255, 255, 16), width=1)


async def build(character_id: int, locale: str, output: Path):
    client = NanokaClient(language=locale)
    character = await client.get_character(character_id, include_details=True, refresh=False)
    if character is None or character.detail is None:
        raise SystemExit(f"Character {character_id} not found")
    detail = character.detail
    summary = character.summary
    version = client.version
    stats = max_stats(detail)
    bonuses = bonus_stats(detail, locale)

    catalog = json.loads((client.cache_path / "data" / "character.json").read_text(encoding="utf-8"))
    items = json.loads((client.cache_path / "data" / "item.json").read_text(encoding="utf-8"))
    record = catalog.get(str(character_id)) or {}
    name = clean_localized(character.display_name(locale), locale) or record.get(locale) or record.get("en") or str(character_id)
    desc = clean_localized(detail.desc or record.get("desc") or "", locale)

    splash_path = asset(client, "avatardrawcard", character_id)
    splash = load_webp(splash_path)
    element_icon = load_webp(asset(client, "element", detail.element or ""))
    path_icon = load_webp(asset(client, "pathicon", detail.path_codename or ""))

    icons = {}
    for stat in detail.stats.values():
        for cost in stat.cost:
            icons[cost.item_id] = asset(client, "itemfigures", cost.item_id)
    for trace in detail.traces:
        for level in trace.levels:
            for cost in level.material_list:
                icons[cost.item_id] = icons.get(cost.item_id) or asset(client, "itemfigures", cost.item_id)

    ascension = aggregate([cost for stat in detail.stats.values() for cost in stat.cost])
    skill_costs = skill_materials(detail)
    trace_costs = aggregate(
        [cost for pid in ("point06", "point07", "point08") for level in detail.skill_trees.get(pid, {}).values() for cost in level.material_list]
    )

    img = Image.new("RGBA", (W, H), BG)
    img.alpha_composite(radial((1600, 1400), (116, 68, 205), 0.32), (-430, -620))
    img.alpha_composite(radial((1100, 1100), (217, 87, 57), 0.18), (1200, -420))
    draw = ImageDraw.Draw(img)

    header_h = 790
    draw.rectangle((0, 0, W, header_h), fill=(12, 8, 23, 255))
    draw.line((M, 112, W - M, 112), fill=LINE, width=1)
    draw.text((M, 55), "NANOKA / HSR  /  CHARACTER ARCHIVE", font=font(21, bold=True), fill=MUTED)

    if splash:
        target_h = 745
        scale = target_h / splash.height
        splash = splash.resize((round(splash.width * scale), target_h), Image.Resampling.LANCZOS)
        splash_x = W - M - splash.width + 170
        splash_y = 56
        glow = radial((900, 900), (246, 172, 87), 0.17)
        img.alpha_composite(glow, (splash_x - 60, 70))
        # The source art already has a clean alpha silhouette; preserve it instead of
        # baking rectangular fade bands into the header.
        img.alpha_composite(splash, (splash_x, splash_y))

    # Draw the version badge after the splash so it remains legible over the art.
    vf = font(18, bold=True)
    vtext = f"DATA v{version}   /   {locale.upper()}"
    vw = draw.textlength(vtext, font=vf)
    composite_panel(img, (W - M - vw - 42, 42, W - M, 88), 23, (19, 13, 33, 245), (255, 255, 255, 70))
    draw.text((W - M - vw - 21, 54), vtext, font=vf, fill=TEXT)

    x = M
    y = 178
    path_label = PATH_NAMES.get((detail.path_codename or "").lower(), (detail.path or "").title())
    composite_panel(img, (x, y, x + 470, y + 44), 22, (255, 255, 255, 18), (255, 255, 255, 34))
    draw.text((x + 22, y + 9), f"PATH: {path_label.upper()}", font=font(17, bold=True), fill=MUTED)
    y += 78

    title = name.upper() if locale == "en" else name
    title_f = font(112 if len(name) <= 15 else 92, display=True, locale=locale)
    title_lines = wrap(draw, title, title_f, 1040)
    for line in title_lines[:2]:
        draw.text((x, y), line, font=title_f, fill=TEXT)
        y += 124

    y += 4
    for i in range(summary.stars or 5):
        make_star(img, x + 18 + i * 38, y + 17, 15, GOLD)

    y += 62
    tag_x = x
    for label, icon in (("FIRE", element_icon), ("NIHILITY", path_icon)):
        if icon:
            small = icon.resize((34, 34), Image.Resampling.LANCZOS)
            canvas_x = int(tag_x)
            tag_width = rounded_tag(img, draw, (canvas_x + 50, y), label, FIRE)
            img.alpha_composite(small, (canvas_x, y + 4))
            tag_x += tag_width + 70
        else:
            tag_width = rounded_tag(img, draw, (tag_x, y), label, FIRE)
            tag_x += tag_width + 18

    y += 70
    desc_font = font(21, locale=locale)
    desc_lines = wrap(draw, desc, desc_font, 930)[:4]
    for line in desc_lines:
        draw.text((x, y), line, font=desc_font, fill=MUTED)
        y += 33

    top = 820
    draw.rectangle((0, top - 56, W, H), fill=(11, 7, 21, 255))
    draw.line((M, top - 56, W - M, top - 56), fill=(255, 255, 255, 28), width=1)

    # BASE STATS
    card_x, card_y, card_w, card_h = M, top + 50, 690, 260
    section_title(draw, card_x, top - 4, "BASE STATS", "MAX LEVEL 80", card_w)
    composite_panel(img, (card_x, card_y, card_x + card_w, card_y + card_h), 24)
    sx, sy = card_x + 32, card_y + 36
    primary = [("HP", round(stats["hp"])), ("ATK", round(stats["atk"])), ("DEF", round(stats["def"]))]
    for index, (label, value) in enumerate(primary):
        cx = sx + index * 210
        draw.text((cx, sy), label, font=font(16, bold=True), fill=DIM)
        draw.text((cx, sy + 26), f"{value:,}", font=font(48, display=True), fill=TEXT)
    draw.line((sx, sy + 103, card_x + card_w - 32, sy + 103), fill=LINE, width=1)
    secondary = [("SPD", f'{stats["spd"]:g}'), ("CRIT RATE", f'{stats["crit"]:g}%'), ("CRIT DMG", f'{stats["crit_dmg"]:g}%'), ("AGGRO", f'{stats["aggro"]:g}')]
    for index, (label, value) in enumerate(secondary):
        cx = sx + index * 156
        draw.text((cx, sy + 124), label, font=font(13, bold=True), fill=DIM)
        draw.text((cx, sy + 146), value, font=font(26, display=True), fill=TEXT)
    draw.text((sx, card_y + card_h - 30), "Nanoka character data", font=font(12), fill=DIM)

    # VOICE CAST
    voice_x, voice_w = card_x + card_w + 38, 690
    section_title(draw, voice_x, top - 4, "VOICE CAST", None, voice_w)
    composite_panel(img, (voice_x, card_y, voice_x + voice_w, card_y + card_h), 24)
    va = detail.chara_info.va
    voice_entries = [("ENGLISH", va.english), ("CHINESE", va.chinese), ("JAPANESE", va.japanese), ("KOREAN", va.korean)]
    vx, vy = voice_x + 30, card_y + 32
    for index, (label, value) in enumerate(voice_entries):
        col = index % 2
        row = index // 2
        cx = vx + col * 324
        cy = vy + row * 96
        composite_panel(img, (cx, cy, cx + 300, cy + 78), 14, (255, 255, 255, 16), (255, 255, 255, 22))
        draw.text((cx + 16, cy + 10), label, font=font(12, bold=True), fill=DIM)
        display_value = clean_localized(value, locale) if value else "Not credited"
        draw.text((cx + 16, cy + 34), display_value, font=font(18, locale=locale), fill=TEXT if value else DIM)
    draw.text((vx, card_y + card_h - 30), "Character voice cast data", font=font(12), fill=DIM)

    # TOTAL STAT BONUS
    bonus_x = voice_x + voice_w + 38
    bonus_w = W - M - bonus_x
    section_title(draw, bonus_x, top - 4, "TOTAL STAT BONUS", "MINOR TRACES", bonus_w)
    composite_panel(img, (bonus_x, card_y, bonus_x + bonus_w, card_y + card_h), 24)
    bonus_rows = bonuses[:4]
    slots = max(1, len(bonus_rows))
    slot_w = (bonus_w - 56) // slots
    for index, (label, value) in enumerate(bonus_rows):
        cx = bonus_x + 28 + index * slot_w
        draw.text((cx, card_y + 64), label.upper(), font=font(12, bold=True, locale=locale), fill=DIM)
        draw.text((cx, card_y + 88), f"{value:g}%", font=font(40, display=True), fill=PURPLE if index == 2 else TEXT)
        if index < slots - 1:
            draw.line((cx + slot_w - 20, card_y + 56, cx + slot_w - 20, card_y + 148), fill=(255, 255, 255, 18), width=1)
    draw.text((bonus_x + 28, card_y + card_h - 30), "Minor trace bonuses only", font=font(12), fill=DIM)

    # MATERIAL PANELS: two rows, each row split in half
    section_gap = 38
    mat_w = (W - M * 2 - section_gap) // 2
    mat_top = top + 368
    mat_h = 258
    mat_sets = (("ASCENSION MATERIALS", "LV. 1 - 80", ascension), ("SKILL MATERIALS", "ALL SKILLS TO LV. 10", skill_costs))
    for index, (label, subtitle, costs) in enumerate(mat_sets):
        px = M + index * (mat_w + section_gap)
        section_title(draw, px, mat_top - 38, label, subtitle, mat_w)
        composite_panel(img, (px, mat_top, px + mat_w, mat_top + mat_h), 24)
        credits = next((cost.amount for cost in costs if cost.item_id == 2), 0)
        draw.text((px + 28, mat_top + 20), "TOTAL CREDITS", font=font(12, bold=True), fill=DIM)
        draw.text((px + 28, mat_top + 38), f"{credits:,}", font=font(34, display=True), fill=TEXT)
        icon = load_webp(icons.get(2), (38, 38))
        if icon:
            img.alpha_composite(icon, (px + mat_w - 66, mat_top + 28))
        draw.line((px + 28, mat_top + 90, px + mat_w - 28, mat_top + 90), fill=LINE, width=1)
        filtered = [cost for cost in costs if cost.item_id != 2]
        columns = 2 if len(filtered) > 4 else 1
        rows = math.ceil(len(filtered) / columns)
        col_w = (mat_w - 56) // columns
        for row, cost in enumerate(filtered):
            col = row // rows
            row_index = row % rows
            cx = px + 28 + col * col_w
            row_y = mat_top + 106 + row_index * 40
            material_icon = load_webp(icons.get(cost.item_id), (28, 28))
            if material_icon:
                img.alpha_composite(material_icon, (cx, row_y - 2))
            item_name = material_name(items, cost.item_id, locale)
            fnt = font(14, locale=locale)
            max_name = col_w - 28 - 76
            if draw.textlength(item_name, font=fnt) > max_name:
                while item_name and draw.textlength(item_name + "...", font=fnt) > max_name:
                    item_name = item_name[:-1]
                item_name = item_name.rstrip() + "..."
            draw.text((cx + 38, row_y), item_name, font=fnt, fill=TEXT)
            qty = f"x{cost.amount:,}"
            qf = font(14, bold=True)
            draw.text((cx + col_w - 18 - draw.textlength(qty, font=qf), row_y), qty, font=qf, fill=GOLD)

    draw.line((M, H - 58, W - M, H - 58), fill=LINE, width=1)
    draw.text((M, H - 42), f"NANOKA HSR  /  DATA v{version}  /  {locale.upper()}", font=font(13, bold=True), fill=DIM)
    footer = "CHARACTER INFO CARD  /  01"
    fw = draw.textlength(footer, font=font(13, bold=True))
    draw.text((W - M - fw, H - 42), footer, font=font(13, bold=True), fill=DIM)

    await client.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output, quality=96, subsampling=0)
    print(f"{output} ({output.stat().st_size:,} bytes)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("character_id", type=int)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--out", type=Path, default=Path("out/info.png"))
    args = parser.parse_args()
    asyncio.run(build(args.character_id, args.locale, args.out))


if __name__ == "__main__":
    main()