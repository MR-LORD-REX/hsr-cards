"""Draw comparison highlights and badges shared by stats and skill cards."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from hsr_cards.renderer.nanoka.skills.styles import WEIGHT_SEMI
from hsr_cards.renderer.nanoka.skills.typography import font_w


def change_overlay(canvas, box, *, radius: int = 18) -> None:
    """Tint a changed comparison block without obscuring its contents."""
    x0, y0, x1, y1 = (round(value) for value in box)
    layer = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(
        (0, 0, layer.width - 1, layer.height - 1),
        radius=radius,
        fill=(142, 216, 168, 22),
        outline=(142, 216, 168, 52),
        width=1,
    )
    canvas.alpha_composite(layer, (x0, y0))


def change_badge(draw, x: int, y: int, text: str = "CHANGED", locale: str = "en") -> None:
    """Draw a measured comparison badge at pixel x/y, defaulting to CHANGED with the locale font."""
    fnt = font_w(9, WEIGHT_SEMI, locale)
    width = draw.textlength(text, font=fnt) + 14
    draw.rounded_rectangle(
        (x, y, x + width, y + 16),
        radius=8,
        fill=(142, 216, 168, 24),
        outline=(142, 216, 168, 68),
        width=1,
    )
    draw.text((x + 7, y + 3), text, font=fnt, fill=(142, 216, 168, 255))
