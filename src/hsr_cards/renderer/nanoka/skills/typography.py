"""Select and cache weighted character fonts, including symbol fallbacks."""
from __future__ import annotations

from functools import lru_cache
from hsr_cards.utils.hsrfonts import fontpath, load_font
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.skills.models import SkillData
from hsr_cards.renderer.nanoka.skills.styles import FALLBACK_CHARS, FONT_SEMI_FILE, FONT_SYMBOLS, WEIGHT_BOLD, WEIGHT_REGULAR, WEIGHT_SEMI, _font_cache


@lru_cache(maxsize=48)
def symbol_font(size: int):
    """Use an installed symbol face or the packaged game font, then bundled DIN."""
    return load_font(size, (
        FONT_SYMBOLS, "NotoSansSymbols2-Regular.ttf", "DejaVuSans.ttf",
        fontpath / "optimized_global_web.woff2",
    ))


def font_w(size: int, weight: str = WEIGHT_REGULAR, locale: str = "en", text: str = ""):
    """Return a cached font at pixel size/weight/locale, selecting symbol fallback faces when needed; bundled font-file errors propagate."""
    key = (size, weight, locale)
    if locale == "en" and any(char in FALLBACK_CHARS for char in text):
        key = (size, weight, "symbols")
    if key in _font_cache:
        return _font_cache[key]
    if key[2] == "symbols":
        result = symbol_font(size)
    elif locale == "en" and weight == WEIGHT_SEMI:
        result = load_font(size, (FONT_SEMI_FILE,), fallback="medium")
    else:
        result = font(size, bold=weight == WEIGHT_BOLD, locale=locale)
    _font_cache[key] = result
    return result


def title_font(size: int, data: SkillData, text: str = ""):
    """Return a bold skill-title font, selecting an English symbol fallback for unsupported glyphs."""
    if data.locale == "en" and any(char in FALLBACK_CHARS for char in text):
        return symbol_font(size)
    return font(size, bold=True, locale=data.locale)


def title_runs(draw, text: str, size: int, data: SkillData, x: int, y: int, fill=TEXT):
    """Draw title runs with per-glyph symbol fallback at x/y and return their total pixel width."""
    base = font(size, bold=True, locale=data.locale)
    symbol = symbol_font(size)
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
