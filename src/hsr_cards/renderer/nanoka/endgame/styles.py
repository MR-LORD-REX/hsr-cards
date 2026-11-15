"""Palette, dimensions, and fonts for Nanoka endgame cards."""
from __future__ import annotations
import functools
from pathlib import Path
from PIL import ImageFont
from ....utils.hsrfonts import HSRFonts
W = 1080
M = 40
GAP = 20
BG = (10, 10, 20, 255)
BG2 = (15, 14, 28, 255)
PANEL = (26, 23, 42, 255)
PANEL2 = (32, 28, 51, 255)
EDGE = (66, 56, 92, 255)
TEXT = (246, 243, 252, 255)
BODY = (225, 220, 238, 255)
MUTED = (184, 177, 202, 255)
GOLD = (255, 205, 121, 255)
PURPLE = (198, 169, 255, 255)
CYAN = (146, 226, 238, 255)
RED = (255, 146, 154, 255)
LIVE = (146, 235, 178, 255)
UPCOMING = (255, 205, 121, 255)
ENDED = (184, 177, 202, 255)

ELEMENT_COLORS = {
    "physical": (238, 238, 238, 255), "fire": (255, 142, 102, 255),
    "ice": (133, 211, 255, 255), "thunder": (206, 145, 255, 255),
    "wind": (123, 232, 170, 255), "quantum": (138, 130, 255, 255),
    "imaginary": (255, 223, 115, 255),
}
ELEMENT_LABELS = {name: name.title() for name in ELEMENT_COLORS}
ICON_GLYPHS = {"physical": "z", "fire": "v", "ice": "w", "thunder": "y", "wind": "t", "quantum": "u", "imaginary": "x", "star": "b"}
ICON_FONT_PATH = Path(__file__).resolve().parents[3] / "assets" / "fonts" / "hsr-icon.ttf"


def font(size: int, weight: str = "medium"):
    """Load a packaged HSR font at pixel size and weight; invalid weights or unreadable font files raise errors."""
    return HSRFonts.get_font(size, weight)  # type: ignore[arg-type]


@functools.lru_cache(maxsize=32)
def icon_font(size: int):
    """Return a cached icon-symbol font at pixel size; missing/unreadable packaged fonts raise OSError."""
    return ImageFont.truetype(str(ICON_FONT_PATH), size)
