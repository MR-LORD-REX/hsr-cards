"""Packaged fonts and optional system faces, loaded only while rendering."""
from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
from typing import Iterable, Literal

from PIL import ImageFont

fontpath = Path(__file__).parent.parent / "assets" / "fonts"
WINDOWS_FONT_DIR = Path(os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:/Windows") / "Fonts"
FontWeight = Literal["bold", "light", "medium", "regular"]


class HSRFonts:
    FONTS: dict[str, str] = {
        "bold": str(fontpath / "DIN-Bold.ttf"),
        "light": str(fontpath / "DIN-Light.ttf"),
        "medium": str(fontpath / "DIN-Medium.ttf"),
        "regular": str(fontpath / "DIN-Regular.ttf"),
    }

    @staticmethod
    def get_font(size: int, type: FontWeight) -> ImageFont.FreeTypeFont:
        """Open a bundled DIN face; invalid weights and font-file errors propagate."""
        font_path = HSRFonts.FONTS.get(type)
        if font_path is None:
            raise ValueError(f"Invalid font type: {type}")
        try:
            return ImageFont.truetype(font_path, size)
        except OSError as exc:
            raise OSError(f"Cannot load bundled font: {font_path}") from exc


@lru_cache(maxsize=2)
def _woff_font_bytes(path: str) -> bytes:
    """Decode a local WOFF2 into reusable TTF bytes without writing a temporary file."""
    from fontTools.ttLib import TTFont, TTLibError

    try:
        with TTFont(path) as face:
            face.flavor = None
            buffer = BytesIO()
            face.save(buffer)
            return buffer.getvalue()
    except TTLibError as exc:
        raise OSError(f"Cannot decode font: {path}") from exc


def load_font(
    size: int, candidates: Iterable[str | Path], *, fallback: FontWeight = "regular",
) -> ImageFont.FreeTypeFont:
    """Try optional font paths/names, then open the packaged face of the requested weight.

    Pillow resolves bare names in platform font directories. Missing or unreadable
    optional fonts are skipped. Packaged fallback errors remain explicit.
    """
    for candidate in candidates:
        try:
            if Path(candidate).suffix.lower() == ".woff2":
                return ImageFont.truetype(BytesIO(_woff_font_bytes(str(candidate))), size)
            return ImageFont.truetype(str(candidate), size)
        except (ImportError, OSError, ValueError):
            continue
    return HSRFonts.get_font(size, fallback)
