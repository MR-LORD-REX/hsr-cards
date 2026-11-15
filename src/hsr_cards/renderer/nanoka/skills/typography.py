"""Select and cache weighted character fonts, including symbol fallbacks."""
from __future__ import annotations

from PIL import ImageFont
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.skills.models import SkillData
from hsr_cards.renderer.nanoka.skills.styles import FALLBACK_CHARS, FONT_SEMI_FILE, FONT_SYMBOLS, WEIGHT_BOLD, WEIGHT_REGULAR, WEIGHT_SEMI, _font_cache


def font_w(size: int, weight: str = WEIGHT_REGULAR, locale: str = "en", text: str = ""):
    """Return a cached font at pixel size/weight/locale, selecting symbol fallback faces when needed; font-file errors propagate."""
    key = (size, weight, locale)
    if locale == "en" and any(char in FALLBACK_CHARS for char in text) and FONT_SYMBOLS.exists():
        key = (size, weight, "symbols")
    if key in _font_cache:
        return _font_cache[key]
    if key[2] == "symbols":
        result = ImageFont.truetype(str(FONT_SYMBOLS), size)
    elif locale == "en" and weight == WEIGHT_SEMI and FONT_SEMI_FILE.exists():
        result = ImageFont.truetype(str(FONT_SEMI_FILE), size)
    else:
        result = font(size, bold=weight == WEIGHT_BOLD, locale=locale)
    _font_cache[key] = result
    return result


def title_font(size: int, data: SkillData, text: str = ""):
    """Return a bold skill-title font, selecting an English symbol fallback for unsupported glyphs."""
    if data.locale == "en" and any(char in FALLBACK_CHARS for char in text) and FONT_SYMBOLS.exists():
        return ImageFont.truetype(str(FONT_SYMBOLS), size)
    return font(size, bold=True, locale=data.locale)


def title_runs(draw, text: str, size: int, data: SkillData, x: int, y: int, fill=TEXT):
    """Draw title runs with per-glyph symbol fallback at x/y and return their total pixel width."""
    base = font(size, bold=True, locale=data.locale)
    symbol = ImageFont.truetype(str(FONT_SYMBOLS), size) if FONT_SYMBOLS.exists() else base
    run = ""
    run_symbols = False
    cursor = float(x)
    for char in text:
        is_symbol = data.locale == "en" and char in FALLBACK_CHARS
        if run and is_symbol != run_symbols:
            face = symbol if run_symbols else base
            draw.text((cursor, y), run, font=face, fill=fill)
            cursor += draw.textlength(run, font=face)
            run = ""
        run += char
        run_symbols = is_symbol
    if run:
        face = symbol if run_symbols else base
        draw.text((cursor, y), run, font=face, fill=fill)
        cursor += draw.textlength(run, font=face)
    return cursor - x
