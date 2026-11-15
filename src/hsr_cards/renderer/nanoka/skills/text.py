"""Tokenize descriptions and measure/draw locale-aware mixed text runs."""
from __future__ import annotations

from PIL import ImageFont
import math
import re
from hsr_cards.renderer.nanoka.skills.models import GlossaryTerm, Piece, RankRow, SkillGroup, SkillRow
from hsr_cards.renderer.nanoka.skills.preparation import format_number, group_columns, normalize_breaks, value_kind
from hsr_cards.renderer.nanoka.skills.styles import BODY, CHANGED_VALUE_KINDS, DESC_TARGET_H, EIDOLON_VALUE, FALLBACK_CHARS, FONT_SYMBOLS, KIND_COLOR, KIND_WEIGHT, MAX_PARTS, MECHANIC, MECHANIC_RE, PARAM_RE, PUNCT_ONLY, QUOTE, TAG_RE, VALUE, VALUE_KINDS, WEIGHT_REGULAR
from hsr_cards.renderer.nanoka.skills.typography import font_w, symbol_font


def _runs_to_pieces(runs) -> list[Piece]:
    pieces: list[Piece] = []
    for text, kind, color in runs:
        if not text:
            continue
        pieces.append(
            Piece(text, color, KIND_WEIGHT.get(kind, WEIGHT_REGULAR), kind.startswith("removed"))
        )
    return pieces


def plain_tokens(text: str, *, keep_newlines: bool = True) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Return (text, kind, RGBA color) runs, highlighting quoted/mechanic text and optionally retaining paragraph breaks."""
    text = TAG_RE.sub("", text).replace("\\n", "\n") if keep_newlines else TAG_RE.sub("", text).replace("\\n", " ")
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    position = 0

    def boundary(previous: str, following: str) -> bool:
        return bool(previous) and bool(following) and not previous.isspace() and not following.isspace()

    def emit(match_start: int, match_end: int, group: int):
        nonlocal position
        if match_start > position:
            tokens.extend(plain_leaf(text[position:match_start]))
        if match_start > 0 and boundary(text[match_start - 1], text[match_start]):
            tokens.append((" ", "plain", BODY))
        tokens.append((text[match_start:match_end], "quote" if group == 1 else "mechanic",
                       QUOTE if group == 1 else MECHANIC))
        if match_end < len(text) and boundary(text[match_end - 1], text[match_end]):
            tokens.append((" ", "plain", BODY))
        position = match_end

    for match in MECHANIC_RE.finditer(text):
        emit(match.start(), match.end(), 1 if match.group(1) else 3)
    if position < len(text):
        tokens.extend(plain_leaf(text[position:]))
    return tokens


def plain_leaf(text: str) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Split ordinary text into plain runs while retaining actual/escaped newline tokens."""
    parts = re.split(r"(\n|\\n)", text)
    result = []
    for part in parts:
        if part in ("\n", "\\n"):
            result.append(("\n", "plain", BODY))
        elif part:
            result.append((part, "plain", BODY))
    return result


def text_units(text: str, locale: str) -> list[tuple[str, bool]]:
    """Return (wrapping unit, preceding-space flag) pairs; Chinese/Japanese split by glyph and punctuation stays attached."""
    if not text:
        return []
    if locale in ("zh", "ja"):
        pattern = re.compile(r"\s+|[\u4e00-\u9fff\u3040-\u30ff]|[^\s\u4e00-\u9fff\u3040-\u30ff]+")
        tokens = pattern.findall(text)
    else:
        tokens = re.findall(r"\s+|[^\s]+", text)
    units: list[tuple[str, bool]] = []
    pending_space = False
    for token in tokens:
        if token.isspace():
            pending_space = True
            continue
        if units and PUNCT_ONLY.match(token):
            units[-1] = (units[-1][0] + token, units[-1][1])
            continue
        if units and token.startswith("(") and PUNCT_ONLY.match(token[1:] or "x"):
            units[-1] = (units[-1][0] + token, units[-1][1])
            continue
        units.append((token, pending_space))
        pending_space = False
    return units


def description_tokens(group: SkillGroup) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Return existing comparison runs or expanded skill-description runs with colored values and table markers."""
    if group.diff_runs is not None:
        return group.diff_runs
    return desc_tokens(group.raw_desc or group.desc or "", {row.index: row for row in group.rows}, VALUE, group_columns(group))


def desc_tokens(raw: str, by_id: dict[int, SkillRow], color, columns: dict[int, str] | None = None) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Expand styled description placeholders into (text, kind, RGBA color) runs.

    by_id supplies one-based SkillRows; optional columns adds alphabetical table
    markers. Preserve paragraph breaks and formatting kinds; missing values become
    visible parameter markers. This function does not measure, draw or fetch data.
    """
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    raw = normalize_breaks(raw or "")
    position = 0
    for match in PARAM_RE.finditer(raw):
        if match.start() > position:
            tokens.extend(plain_tokens(raw[position:match.start()]))
        index = int(match.group(1))
        row = by_id.get(index)
        suffix = match.group(3) or ""
        if row is None:
            tokens.append((f"#{index}{suffix}", "value", color))
        else:
            prefix = " " if match.start() > 0 and not raw[match.start() - 1].isspace() else ""
            kind = value_kind(row.style)
            label = columns.get(index) if columns else None
            suffix_text = f" ({label})" if label else ""
            tokens.append((f"{prefix}{row.default_display}{suffix_text}", kind, KIND_COLOR[kind]))
        position = match.end()
    if position < len(raw):
        tokens.extend(plain_tokens(raw[position:]))
    return [token for token in tokens if token[0]]


def eidolon_tokens(rank: RankRow) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Expand an eidolon's parameter displays into colored text runs, preserving paragraph breaks and unknown markers."""
    raw = normalize_breaks(rank.raw_desc or rank.desc or "")
    by_id = {index: (display, style) for index, display, style in rank.params}
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    position = 0
    for match in PARAM_RE.finditer(raw):
        if match.start() > position:
            tokens.extend(plain_tokens(raw[position:match.start()]))
        index = int(match.group(1))
        prefix = " " if match.start() > 0 and not raw[match.start() - 1].isspace() else ""
        if index in by_id:
            display, style = by_id[index]
            kind = value_kind(style)
            tokens.append((f"{prefix}{display}", kind, KIND_COLOR[kind]))
        else:
            tokens.append((f"{prefix}#{index}{match.group(3) or ''}", "value", EIDOLON_VALUE))
        position = match.end()
    if position < len(raw):
        tokens.extend(plain_tokens(raw[position:]))
    return [token for token in tokens if token[0]]


def glossary_tokens(term: GlossaryTerm) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Expand a glossary entry's numeric params into styled runs, leaving unknown indices visible."""
    raw = normalize_breaks(term.desc or "")
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    position = 0
    for match in PARAM_RE.finditer(raw):
        if match.start() > position:
            tokens.extend(plain_tokens(raw[position:match.start()]))
        index = int(match.group(1))
        style = match.group(2) + (match.group(3) or "")
        prefix = " " if match.start() > 0 and not raw[match.start() - 1].isspace() else ""
        if 1 <= index <= len(term.params):
            text = format_number(term.params[index - 1], style)
            kind = value_kind(style)
        else:
            text = f"#{index}"
            kind = "value"
        tokens.append((f"{prefix}{text}", kind, KIND_COLOR.get(kind, VALUE)))
        position = match.end()
    if position < len(raw):
        tokens.extend(plain_tokens(raw[position:]))
    return [token for token in tokens if token[0]]


def layout_lines(draw, runs, width: int, size: int, locale: str) -> list[list[Piece]]:
    """Wrap colored/diff runs to pixel width as lists of Piece objects.

    size/locale select measured font faces; punctuation and column markers remain
    attached to preceding words. Removed runs carry strikethrough metadata. The
    function reads packaged fonts but does not draw or perform provider requests.
    """
    lines: list[list[Piece]] = [[]]
    line_w = 0.0
    space_w = draw.textlength(" ", font=font_w(size, WEIGHT_REGULAR, locale, " "))

    def add_piece(piece: Piece, space_before: bool):
        nonlocal line_w
        if not piece.text:
            return
        # Diff runs arrive one token at a time, so punctuation can meet the
        # wrapping pass as a separate unit. Glue it to the preceding word
        # instead of rendering "Energy ." with a stray space.
        punctuation = bool(PUNCT_ONLY.fullmatch(piece.text)) or bool(
            piece.text.startswith("(") and PUNCT_ONLY.fullmatch(piece.text[1:] or "x")
        )
        if punctuation and lines[-1] and line_w > 0:
            previous = lines[-1][-1]
            previous.text += piece.text
            line_w += measure_text_mixed(draw, piece.text, size, piece.weight, locale)
            return
        unit_w = measure_text_mixed(draw, piece.text, size, piece.weight, locale)
        gap = space_w if space_before and line_w > 0 else 0.0
        if line_w > 0 and line_w + gap + unit_w > width + 0.5:
            lines.append([])
            line_w = 0.0
            gap = 0.0
        if gap:
            lines[-1].append(Piece(" ", piece.color, WEIGHT_REGULAR))
            line_w += gap
        lines[-1].append(piece)
        line_w += unit_w

    for text, kind, color in runs:
        if text == "\n":
            lines.append([])
            line_w = 0.0
            continue
        weight = KIND_WEIGHT.get(kind, WEIGHT_REGULAR)
        strike = kind.startswith("removed")
        if kind in VALUE_KINDS or kind in CHANGED_VALUE_KINDS:
            add_piece(Piece(text, color, weight, strike), True)
            continue
        for unit, space_before in text_units(text, locale):
            add_piece(Piece(unit, color, weight, strike), space_before or bool(lines[-1]))

    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    if len(lines) == 1 and not lines[0]:
        return []
    return lines


def measure_lines(lines: list[list[Piece]], line_h: int) -> int:
    """Return the laid-out line count multiplied by line_h pixels."""
    return len(lines) * line_h


def trim_blank_lines(lines: list[list[Piece]]) -> list[list[Piece]]:
    """Return laid-out lines with empty leading/trailing rows removed, preserving interior paragraph gaps."""
    while lines and not lines[0]:
        lines = lines[1:]
    while lines and not lines[-1]:
        lines = lines[:-1]
    return lines


def measure_text_mixed(draw, text: str, size: int, weight: str, locale: str) -> float:
    """Measure a string with the same per-run fallback faces used to draw it."""
    base = font_w(size, weight, locale)
    symbol = symbol_font(size)
    run = ""
    run_symbols = False
    width = 0.0
    for char in text:
        is_symbol = locale == "en" and char in FALLBACK_CHARS
        if run and is_symbol != run_symbols:
            face = symbol if run_symbols else base
            width += draw.textlength(run, font=face)
            run = ""
        run += char
        run_symbols = is_symbol
    if run:
        face = symbol if run_symbols else base
        width += draw.textlength(run, font=face)
    return width


def draw_text_runs(draw, text: str, x: int, y: int, size: int, weight: str, color, locale: str) -> float:
    """Draw a string while switching only the glyphs that need a fallback face."""
    base = font_w(size, weight, locale)
    symbol = symbol_font(size)
    run = ""
    run_symbols = False
    cursor = float(x)
    for char in text:
        is_symbol = locale == "en" and char in FALLBACK_CHARS
        if run and is_symbol != run_symbols:
            face = symbol if run_symbols else base
            draw.text((cursor, y), run, font=face, fill=color)
            cursor += draw.textlength(run, font=face)
            run = ""
        run += char
        run_symbols = is_symbol
    if run:
        face = symbol if run_symbols else base
        draw.text((cursor, y), run, font=face, fill=color)
        cursor += draw.textlength(run, font=face)
    return cursor


def draw_lines(draw, lines, x: int, y: int, size: int, line_h: int, locale: str = "en", max_lines: int | None = None) -> int:
    """Draw premeasured Piece rows with colors/weights/strikethroughs and return consumed pixel height; max_lines optionally truncates."""
    if max_lines is not None:
        lines = lines[:max_lines]
    for line_index, line in enumerate(lines):
        line_x = float(x)
        for piece in line:
            line_y = y + line_index * line_h
            if locale == "en" and any(char in FALLBACK_CHARS for char in piece.text):
                end_x = draw_text_runs(draw, piece.text, line_x, line_y, size, piece.weight, piece.color, locale)
            else:
                piece_font = font_w(size, piece.weight, locale, piece.text)
                draw.text((line_x, line_y), piece.text, font=piece_font, fill=piece.color)
                end_x = line_x + draw.textlength(piece.text, font=piece_font)
            if piece.strike and piece.text.strip():
                strike_y = line_y + round(size * 0.55)
                draw.line((line_x, strike_y, end_x, strike_y), fill=piece.color, width=max(1, size // 11))
            line_x = end_x
    return len(lines) * line_h


def split_lines(lines: list[list[Piece]], line_h: int, max_h: int) -> list[list[list[Piece]]]:
    """Partition laid-out rows when their pixel height exceeds max_h, preserving pieces and limiting continuation count."""
    total = len(lines) * line_h
    if total <= max_h or not lines:
        return [lines]
    parts = min(MAX_PARTS, max(2, math.ceil(total / DESC_TARGET_H)))
    per = math.ceil(len(lines) / parts)
    return [lines[index:index + per] for index in range(0, len(lines), per)]


def measure_runs(draw, runs, width: int, size: int, line_h: int, locale: str) -> tuple[int, int]:
    """Return (pixel height, line count) for wrapped rich runs; whitespace-only content returns (0, 0)."""
    if not any(text.strip() for text, _, _ in runs if text != "\n"):
        return 0, 0
    lines = layout_lines(draw, runs, width, size, locale)
    return len(lines) * line_h, len(lines)
