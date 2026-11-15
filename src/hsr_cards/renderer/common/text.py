"""Measured word wrapping shared by card layouts."""
from PIL import ImageDraw


def wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, text_font) -> list[str]:
    """Word-wrap text to max_width pixels using the supplied draw/font metrics.

    Return lines with paragraph separators preserved after existing content.
    Whitespace within paragraphs collapses to spaces; overlong single words remain
    unsplit. The function measures text only and performs no drawing or provider IO.
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            if lines:
                lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=text_font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines
