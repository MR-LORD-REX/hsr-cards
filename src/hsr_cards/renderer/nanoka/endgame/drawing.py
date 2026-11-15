"""Small drawing primitives for the endgame layout."""
from __future__ import annotations
from PIL import Image, ImageDraw
from ...common.text import wrap_text
from .styles import *


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 1):
    """Draw a rounded rectangle into the supplied ImageDraw using pixel bounds, fill and optional outline."""
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, fill) -> None:
    """Draw a five-point star centered at pixel cx/cy with the supplied outer radius and fill."""
    import math
    points = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        factor = 1.0 if index % 2 == 0 else 0.45
        points.append((cx + math.cos(angle) * radius * factor, cy + math.sin(angle) * radius * factor))
    draw.polygon(points, fill=fill)


def draw_chip(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    label: str,
    *,
    color=GOLD,
    size: int = 18,
) -> int:
    """Draw a measured pill label at xy and return its width in pixels; size controls the font."""
    x, y = xy
    text_font = font(size, "bold")
    width = int(draw.textlength(label, font=text_font)) + 26
    rounded(draw, (x, y, x + width, y + 30), 15, (35, 31, 52, 255), (*color[:3], 120))
    draw.text((x + 13, y + 15), label, font=text_font, fill=color, anchor="lm")
    return width


def draw_element_chip(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    element: str,
    icons: dict[str, Image.Image],
) -> int:
    """Draw an element-color/glyph pill at x/y and return its measured width in pixels."""
    color = ELEMENT_COLORS.get(element, MUTED)
    label = ELEMENT_LABELS.get(element, element.title())
    text_font = font(17, "bold")
    width = int(draw.textlength(label, font=text_font)) + 44
    rounded(draw, (x, y, x + width, y + 30), 15, (31, 27, 47, 255), (*color[:3], 100))
    draw.text((x + 9, y + 15), ICON_GLYPHS.get(element, "b"), font=icon_font(19), fill=color, anchor="lm")
    draw.text((x + 33, y + 15), label, font=text_font, fill=color, anchor="lm")
    return width


def _measure_draw() -> ImageDraw.ImageDraw:
    canvas = Image.new("RGBA", (1, 1))
    return ImageDraw.Draw(canvas)


def wrapped_lines(text: str, width: int, size: int = 19) -> int:
    """Return at least one measured bold-text line for a pixel width/font size, using the same wrapper as drawing."""
    draw = _measure_draw()
    return max(1, len(wrap_text(draw, text, max(width, 1), font(size, "bold"))))
