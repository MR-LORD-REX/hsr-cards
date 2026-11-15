"""Nanoka display text and numeric parameter formatting."""
from __future__ import annotations
import math
import re
from typing import Sequence
PARAM_RE = re.compile(r"#(\d+)(?:\[[^\]]*\])?(%)?")
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str:
    """Strip markup, expand escaped/br paragraph breaks and collapse horizontal whitespace; None returns an empty string."""
    if not value:
        return ""
    text = str(value).replace("\\n", "\n").replace("<br>", "\n").replace("<br/>", "\n")
    text = TAG_RE.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def format_number(value: float | int | None) -> str:
    """Return comma-grouped integer/one-decimal display text, or ? for None; nonnumeric values raise conversion errors."""
    if value is None:
        return "?"
    number = float(value)
    if abs(number - round(number)) < 0.01:
        return f"{int(round(number)):,}"
    return f"{number:,.1f}"


def format_hp(value: float | int | None) -> str:
    """Round HP to the nearest integer using half-up rounding and comma grouping; None returns ?."""
    if value is None:
        return "?"
    return f"{math.floor(float(value) + 0.5):,}"


def expand_params(text: str | None, params: Sequence[float | int]) -> str:
    """Expand one-based Nanoka #N placeholders using numeric params.

    Typed placeholders are supported and a trailing % scales ratios by 100.
    Missing indices become empty text; markup is stripped and paragraph breaks are
    preserved. Numeric conversion errors propagate; no provider or file IO occurs.
    """
    clean = clean_text(text)
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(params):
            return ""
        value = float(params[index]) * (100 if match.group(2) else 1)
        rendered = f"{value:g}"
        return rendered + ("%" if match.group(2) else "")
    return re.sub(r"[ \t]+", " ", PARAM_RE.sub(replace, clean)).strip()
