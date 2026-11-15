"""Character info identity, artwork, badges, and comparison drawing primitives."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from hsr_cards.renderer.nanoka.character_info import BG
from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import FIRE
from hsr_cards.renderer.nanoka.character_info import GOLD
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import PURPLE
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import composite_panel
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import make_star
from hsr_cards.renderer.nanoka.character_info import radial
from hsr_cards.renderer.nanoka.character_info import wrap
from hsr_cards.renderer.nanoka.diff import diff_words
from hsr_cards.renderer.nanoka.info.models import CardData
from hsr_cards.renderer.nanoka.info.styles import M
from hsr_cards.renderer.nanoka.info.text import draw_detail_lines, heavy, layout_detail_lines, wrap_text


def base_canvas(width: int, height: int) -> Image.Image:
    """Create a width-by-height RGBA info-card canvas with the palette and radial background glows."""
    img = Image.new("RGBA", (width, height), BG)
    img.alpha_composite(radial((1100, 900), (116, 68, 205), 0.30), (-330, -460))
    img.alpha_composite(radial((800, 800), (217, 87, 57), 0.16), (700, -300))
    return img


def heading(draw, x, y, title, subtitle, width, locale="en", size=24):
    """Draw a localized section heading, right-aligned subtitle and divider within a pixel width."""
    draw.rectangle((x, y + 8, x + 26, y + 12), fill=PURPLE)
    draw.text((x + 38, y - 5), title, font=heavy(size, locale), fill=PURPLE)
    if subtitle:
        sub = font(17, bold=True, locale=locale)
        sw = draw.textlength(subtitle, font=sub)
        draw.text((x + width - sw, y), subtitle, font=sub, fill=DIM)
    draw.line((x, y + 42, x + width - 2, y + 42), fill=LINE, width=1)


def tag(canvas, draw, x, y, label, color, locale="en", size=19, height=42):
    """Draw a colored label pill at x/y and return its measured pixel width."""
    fnt = heavy(size, locale)
    width = draw.textlength(label, font=fnt) + 44
    layer = Image.new("RGBA", (round(width), height), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((0, 0, width - 1, height - 1), radius=height // 2, fill=(*color[:3], 38), outline=(*color[:3], 145), width=1)
    canvas.alpha_composite(layer, (round(x), round(y)))
    draw.text((x + 22, y + 8), label, font=fnt, fill=color)
    return width


def variation_text(data: CardData) -> str:
    """Return single/comparison build labels followed by the uppercase locale."""
    if data.before is not None:
        return f"v{data.before.version} \u2192 v{data.version}  /  {data.locale.upper()}"
    return f"v{data.version}  /  {data.locale.upper()}"


def version_pill(canvas, draw, data: CardData, width: int, y=26):
    """Draw a right-aligned single/comparison version label within the canvas pixel width."""
    vtext = variation_text(data)
    vf = heavy(17, data.locale)
    vw = draw.textlength(vtext, font=vf)
    x0 = width - M - vw - 36
    composite_panel(canvas, (x0, y, width - M, y + 46), 23, (19, 13, 33, 248), (255, 255, 255, 70))
    draw.text((x0 + 18, y + 10), vtext, font=vf, fill=TEXT)


def splash(canvas, data: CardData, target_h: int, x: int, y: int):
    """Scale borrowed character art to target_h pixels and alpha-composite it with a glow at x/y; absent art is a no-op."""
    if not data.splash:
        return
    img = data.splash
    scale = target_h / img.height
    img = img.resize((round(img.width * scale), target_h), Image.Resampling.LANCZOS)
    glow = radial((800, 800), (246, 172, 87), 0.18)
    canvas.alpha_composite(glow, (x - 90, y + 80))
    canvas.alpha_composite(img, (x, y))


def identity(canvas, draw, data: CardData, x: int, y: int, title_size: int, desc_width: int, desc_lines: int):
    """Draw localized identity, rarity and element/path badges with at most desc_lines description rows; comparisons show prior text."""
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
