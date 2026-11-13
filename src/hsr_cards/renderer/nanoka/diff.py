"""Word-level diffs for the Nanoka comparison cards.

Nanoka renders version changes inline: removed text keeps its old wording with
a strikethrough, new text is highlighted. The helpers here compute that same
shape from two version payloads without relying on Nanoka's bundled
``diff/<locale>.json`` (which only describes one fixed predecessor pair).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

EQUAL = "equal"
REMOVED = "removed"
ADDED = "added"
ARROW = "arrow"

ADDED_COLOR = (142, 216, 168, 255)
REMOVED_COLOR = (224, 150, 164, 255)
ARROW_COLOR = (150, 138, 175, 255)

TOKEN_RE = re.compile(r"\s+|[^\s]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff]")
NUMERIC_KINDS = {"percent", "integer", "decimal", "value"}


def tokenize(text: str, locale: str = "en") -> list[str]:
    """Split text into diffable words; CJK text is split per character."""
    if not text:
        return []
    tokens: list[str] = []
    for chunk in re.split(r"(\n)", text):
        if chunk == "\n":
            tokens.append("\n")
            continue
        if not chunk:
            continue
        if locale in ("zh", "ja"):
            for piece in CJK_RE.split(chunk):
                if CJK_RE.fullmatch(piece or ""):
                    tokens.extend(char for char in piece)
                elif piece:
                    tokens.extend(TOKEN_RE.findall(piece))
        else:
            tokens.extend(TOKEN_RE.findall(chunk))
    return tokens


def _words(tokens: Iterable[str]) -> list[str]:
    return [token for token in tokens if token and not token.isspace()]


def diff_words(before: str, after: str, locale: str = "en") -> list[tuple[str, str]]:
    """Return ``(text, kind)`` pairs; whitespace is normalised to single spaces."""
    left = _words(tokenize(before, locale))
    right = _words(tokenize(after, locale))
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    result: list[tuple[str, str]] = []

    def emit(text: str, kind: str) -> None:
        if result and result[-1][1] == kind and kind in {EQUAL, ADDED, REMOVED}:
            result[-1] = (result[-1][0] + " " + text, kind)
            return
        result.append((text, kind))

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for token in left[i1:i2]:
                emit(token, EQUAL)
        elif tag == "delete":
            for token in left[i1:i2]:
                emit(token, REMOVED)
        elif tag == "insert":
            for token in right[j1:j2]:
                emit(token, ADDED)
        elif tag == "replace":
            for token in left[i1:i2]:
                emit(token, REMOVED)
            if i2 > i1 and j2 > j1:
                result.append(("\u2192", ARROW))
            for token in right[j1:j2]:
                emit(token, ADDED)
    return result


def diff_runs(
    before: list[tuple[str, str, tuple[int, int, int, int]]],
    after: list[tuple[str, str, tuple[int, int, int, int]]],
    *,
    locale: str = "en",
    added_color: tuple[int, int, int, int] = ADDED_COLOR,
    removed_color: tuple[int, int, int, int] = REMOVED_COLOR,
    arrow_color: tuple[int, int, int, int] = ARROW_COLOR,
) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    """Diff rich text runs while keeping each side's own colours.

    Runs are ``(text, kind, colour)`` triples. Plain runs are split into
    words; numeric runs stay atomic so a changed number reads as one struck
    token followed by one highlighted token. Changed numbers keep their
    percentage/fixed-value colour so card legends stay meaningful.
    """
    left = _explode(before, locale)
    right = _explode(after, locale)
    # Compare on the words alone: a value that only changes colour/style is
    # still "equal" text, while a changed number still lands as removed+added.
    matcher = SequenceMatcher(
        None, [item[0] for item in left], [item[0] for item in right], autojunk=False
    )
    result: list[tuple[str, str, tuple[int, int, int, int]]] = []

    def add(text: str, kind: str, color) -> None:
        if text == "\n":
            result.append(("\n", "plain", color))
            return
        if not text.strip():
            return
        if result and result[-1][1] == kind and kind not in {ARROW}:
            previous = result[-1]
            result[-1] = (previous[0] + " " + text, previous[1], previous[2])
            return
        if kind in NUMERIC_KINDS:
            kind = _added_kind(kind)
        result.append((text, kind, color))

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for text, kind, color in right[j1:j2]:
                add(text, kind, color)
        elif tag == "delete":
            for text, _kind, _color in left[i1:i2]:
                add(text, REMOVED, removed_color)
        elif tag == "insert":
            for text, kind, color in right[j1:j2]:
                add(text, _added_kind(kind), color if kind in NUMERIC_KINDS else added_color)
        elif tag == "replace":
            for text, kind, color in left[i1:i2]:
                add(text, REMOVED, color if kind in NUMERIC_KINDS else removed_color)
            if i2 > i1 and j2 > j1:
                result.append(("\u2192", ARROW, arrow_color))
            for text, kind, color in right[j1:j2]:
                add(text, _added_kind(kind), color if kind in NUMERIC_KINDS else added_color)
    return result


def _added_kind(kind: str) -> str:
    return f"{ADDED}_{kind}" if kind in NUMERIC_KINDS else ADDED


def _explode(
    runs: list[tuple[str, str, tuple[int, int, int, int]]], locale: str
) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    for text, kind, color in runs:
        if kind in NUMERIC_KINDS:
            tokens.append((text.strip(), kind, color))
            continue
        for token in tokenize(text, locale):
            tokens.append(("\n" if token == "\n" else token, kind, color))
    return tokens


__all__ = [
    "ADDED",
    "ADDED_COLOR",
    "ARROW",
    "ARROW_COLOR",
    "EQUAL",
    "REMOVED",
    "REMOVED_COLOR",
    "diff_runs",
    "diff_words",
    "tokenize",
]