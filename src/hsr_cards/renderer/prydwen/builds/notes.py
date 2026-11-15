"""Paginated complete source conditions and update labels."""
from __future__ import annotations


from pathlib import Path


from .styles import W, H, INK, MUTED, GOLD

from PIL import Image

from ....providers.prydwen.models import BuildCardData


from .primitives import Box, RenderContext, _font, _rule, _text, _wrap


def _dates(data: BuildCardData) -> str:
    meta = data.source_meta
    page = (meta.last_updated if meta else None) or data.character.last_updated or "unknown"
    review = meta.last_review_update if meta else None
    build = meta.last_major_build_update if meta else None
    parts = ["Page: " + page]
    if review:
        parts.append("Review: " + review)
    if build:
        parts.append("Build: " + build)
    return "  |  ".join(parts)


def _notes_pages(ctx: RenderContext, data: BuildCardData, out: Path) -> list[Path]:
    """Paginate exact source conditions; no note is clipped or paraphrased."""
    if not ctx.notes:
        return []
    body_font = _font(28, "source")
    heading_font = _font(29, "bold")
    columns = [64, 992]
    width = 864
    max_y = 1336
    page_no = 1
    col = 0
    y = 184
    pages: list[Path] = []

    def new_page(number: int) -> RenderContext:
        page = RenderContext(Image.new("RGBA", (W, H), (16, 18, 31, 255)), ctx.nanoka, ctx.accent)
        _text(page, data.character.name.upper() + " / CONDITIONS", Box(64, 52, 1792, 64), 44, weight="title", fill=GOLD)
        _text(page, "Exact Prydwen wording • match the numbered references on the build card", Box(64, 126, 1792, 36), 26, fill=MUTED)
        _rule(page, 64, 170, 1792)
        _text(page, f"{data.review.status.value.upper()}  |  PRYDWEN.GG  |  " + _dates(data), Box(64, 1382, 1620, 30), 20, fill=MUTED)
        _text(page, str(number), Box(1730, 1382, 126, 30), 20, fill=GOLD, align="right")
        return page

    page = new_page(page_no)

    def save_page() -> None:
        path = out.with_name(f"{out.stem}.conditions-{page_no:02d}.png")
        page.image.convert("RGB").save(path, "PNG", optimize=True)
        pages.append(path)

    for note in ctx.notes:
        title = f"[{note['id']}] {note['heading']}"
        title_lines = _wrap(title, heading_font, width)
        lines = _wrap(note["text"], body_font, width)
        needed = len(title_lines) * 35 + min(len(lines), 3) * 36 + 28
        if y + needed > max_y:
            col += 1
            y = 184
            if col == 2:
                save_page()
                page_no += 1
                col = 0
                page = new_page(page_no)
        for title_line in title_lines:
            page.draw.text((columns[col], y), title_line, font=heading_font, fill=GOLD, anchor="lt")
            y += 35
        y += 8
        for line in lines:
            if y + 36 > max_y:
                col += 1
                y = 184
                if col == 2:
                    save_page()
                    page_no += 1
                    col = 0
                    page = new_page(page_no)
                page.draw.text((columns[col], y), f"[{note['id']}] continued", font=_font(23, "bold"), fill=GOLD, anchor="lt")
                y += 36
            page.draw.text((columns[col], y), line, font=body_font, fill=INK, anchor="lt")
            y += 36
        y += 32
    save_page()
    return pages

