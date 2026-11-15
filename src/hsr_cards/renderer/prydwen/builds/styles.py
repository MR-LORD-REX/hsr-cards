"""Build-card dimensions, font roots, and palette."""
from pathlib import Path

W, H = 1920, 1440


PACKAGE_ASSETS = Path(__file__).resolve().parents[3] / "assets"


FONT_DIR = Path("C:/Windows/Fonts")


EXTERNAL_FONTS = PACKAGE_ASSETS / "fonts"


INK = (246, 241, 233, 255)


MUTED = (201, 193, 189, 255)


DIM = (155, 151, 158, 255)


GOLD = (231, 199, 144, 255)


LINE = (161, 142, 112, 110)


PANEL = (10, 13, 26, 226)


ACCENTS = {
    "physical": (198, 198, 191), "fire": (255, 137, 122),
    "ice": (133, 220, 250), "lightning": (193, 146, 244),
    "wind": (132, 230, 188), "quantum": (155, 165, 255),
    "imaginary": (245, 217, 143),
}


HSR_GLYPHS = {"lightcone": "Q", "character": "K", "star": "b", "note": "9"}

