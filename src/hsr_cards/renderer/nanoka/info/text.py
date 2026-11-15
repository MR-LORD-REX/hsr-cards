"""Locale-aware wrapping and inline comparison text for character info cards."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import wrap
import re
from hsr_cards.renderer.nanoka.info.models import CardData, DetailPiece
from hsr_cards.renderer.nanoka.info.styles import DETAIL_PUNCT, UI_LABELS


def ui(data: CardData, key: str) -> str:
    """Resolve the info-card UI label in data.locale, falling back to English and then the key."""
    return UI_LABELS.get(data.locale, UI_LABELS["en"]).get(key, UI_LABELS["en"].get(key, key))


def wrap_text(draw, text, fnt, width, locale="en"):
    """Wrap text to measured pixel width using word or Chinese/Japanese glyph boundaries; return display lines."""
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


def heavy(size: int, locale: str = "en", display: bool = False):
    """Load the locale bold font at pixel size, or the English display face when display=True; font errors propagate."""
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


def fit(draw, text, fnt, width):
    """Return measured text shortened with an ellipsis when it exceeds the available pixel width."""
    text = str(text)
    if draw.textlength(text, font=fnt) <= width:
        return text
    suffix = "..."
    while text and draw.textlength(text + suffix, font=fnt) > width:
        text = text[:-1]
    return text.rstrip() + suffix
