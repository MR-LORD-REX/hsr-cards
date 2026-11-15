"""Measured text, fonts, images, and drawing context for build cards."""
from __future__ import annotations



from dataclasses import dataclass, field

from functools import lru_cache


from .styles import W, H, FONT_DIR, EXTERNAL_FONTS, INK, MUTED, GOLD, LINE, PANEL, HSR_GLYPHS

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ....providers.prydwen.models import AssetRef
from ....utils.hsrfonts import load_font

from ....providers.prydwen.assets import NanokaIndex


@dataclass(frozen=True)
class Box:
    """Define an absolute pixel rectangle for a measured drawing operation."""
    x: int
    y: int
    w: int
    h: int


@dataclass
class RenderContext:
    """Keep the resolved image, local asset index, and source-preservation diagnostics for one card."""
    image: Image.Image
    nanoka: NanokaIndex
    accent: tuple[int, int, int]
    exclude_extra: bool = True
    notes: list[dict[str, str]] = field(default_factory=list)
    missing_assets: set[str] = field(default_factory=set)
    clipped_text: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    shown: list[dict[str, str]] = field(default_factory=list)

    @property
    def draw(self) -> ImageDraw.ImageDraw:
        """Return a Pillow drawing context for the current card image."""
        return ImageDraw.Draw(self.image)

    def note(self, key: str, heading: str, text: str | None) -> str:
        """Register an original source condition once and return its reference label.

        Clean cards and empty text return an empty label without adding note pages."""
        text = " ".join((text or "").split())
        if self.exclude_extra or not text:
            return ""
        if not any(item["id"] == key for item in self.notes):
            self.notes.append({"id": key, "heading": heading, "text": text})
        return f"[{key}]"


@lru_cache(maxsize=48)
def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """Use local game/system faces with a bundled fallback; never download a font."""
    if weight == "icon":
        candidates = [EXTERNAL_FONTS / "hsr-icon.ttf"]
    elif weight == "bold":
        candidates = [FONT_DIR / "segoeuib.ttf", FONT_DIR / "arialbd.ttf"]
    elif weight == "title":
        candidates = [FONT_DIR / "bahnschrift.ttf", FONT_DIR / "segoeuib.ttf"]
    elif weight == "source":
        candidates = [FONT_DIR / "segoeui.ttf", FONT_DIR / "arial.ttf"]
    else:
        candidates = [EXTERNAL_FONTS / "optimized_global_web.woff2", FONT_DIR / "segoeui.ttf", FONT_DIR / "arial.ttf"]
    if weight != "icon":
        candidates.extend(
            ("NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf") if weight in ("bold", "title")
            else ("NotoSans-Regular.ttf", "DejaVuSans.ttf")
        )
    return load_font(size, candidates, fallback="bold" if weight in ("bold", "title") else "regular")


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """Wrap words and exceptionally long tokens without painting outside a box."""
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            if font.getlength(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                for char in word:
                    if current and font.getlength(current + char) > width:
                        lines.append(current)
                        current = ""
                    current += char
                continue
            candidate = f"{current} {word}".strip()
            if current and font.getlength(candidate) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def _text(ctx: RenderContext, text: str, box: Box, size: int = 24, *,
          fill=INK, weight: str = "regular", max_lines: int | None = None,
          align: str = "left") -> int:
    font = _font(size, weight)
    if weight == "regular" and any(ord(char) > 126 or char in "\\_`|" for char in text):
        # The supplied WOFF2 is a web subset: bullets, arrows and em dashes
        # are absent. The system font preserves source wording and operators.
        font = _font(size, "source")
    lines = _wrap(text, font, box.w)
    allowed = max(1, box.h // (size + 6))
    if max_lines is not None:
        allowed = min(allowed, max_lines)
    if len(lines) > allowed:
        ctx.clipped_text.append(str(text))
        lines = lines[:allowed]
        tail = lines[-1]
        while tail and font.getlength(tail + "...") > box.w:
            tail = tail[:-1]
        lines[-1] = tail.rstrip() + "..."
    for index, line in enumerate(lines):
        x = box.x
        if align == "center":
            x += (box.w - font.getlength(line)) / 2
        elif align == "right":
            x += box.w - font.getlength(line)
        ctx.draw.text((round(x), box.y + index * (size + 6)), line,
                      font=font, fill=fill, anchor="lt")
    return len(lines) * (size + 6)


def _panel(ctx: RenderContext, box: Box) -> None:
    layer = Image.new("RGBA", ctx.image.size)
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((box.x, box.y, box.x + box.w, box.y + box.h),
                           radius=16, fill=PANEL, outline=LINE, width=2)
    draw.rounded_rectangle((box.x + 10, box.y + 10, box.x + box.w - 10, box.y + box.h - 10),
                           radius=10, outline=(161, 142, 112, 40), width=1)
    ctx.image.alpha_composite(layer)


def _rule(ctx: RenderContext, x: int, y: int, width: int) -> None:
    ctx.draw.line((x, y, x + width, y), fill=LINE, width=1)
    ctx.draw.polygon([(x, y - 3), (x + 3, y), (x, y + 3), (x - 3, y)], fill=GOLD)


def _title(ctx: RenderContext, label: str, x: int, y: int, width: int,
           glyph: str | None = None) -> None:
    offset = 0
    if glyph:
        ctx.draw.text((x, y + 2), HSR_GLYPHS[glyph], font=_font(38, "icon"), fill=GOLD, anchor="lt")
        offset = 48
    _text(ctx, label, Box(x + offset, y, width - offset, 48), 38, weight="title", fill=GOLD)
    _rule(ctx, x, y + 56, width)


def _load(ctx: RenderContext, ref: AssetRef | None) -> Image.Image | None:
    if ref is None:
        ctx.missing_assets.add("unresolved asset reference")
        return None
    path = ctx.nanoka.asset_file(ref)
    if path is None:
        ctx.missing_assets.add(ref.ref)
        return None
    try:
        with Image.open(path) as source:
            return source.convert("RGBA")
    except OSError:
        ctx.missing_assets.add(ref.ref)
        return None


def _icon(ctx: RenderContext, ref: AssetRef | None, box: Box, *, portrait: bool = False) -> None:
    art = _load(ctx, ref)
    if portrait:
        ctx.draw.rounded_rectangle((box.x - 1, box.y - 1, box.x + box.w + 1, box.y + box.h + 1),
                                   radius=10, fill=(39, 33, 47, 255), outline=(*ctx.accent, 150), width=1)
    if art is None:
        ctx.draw.rounded_rectangle((box.x, box.y, box.x + box.w, box.y + box.h), radius=8,
                                   fill=(45, 42, 51, 255), outline=(128, 122, 133, 140))
        _text(ctx, "?", box, min(30, box.h // 2), align="center", fill=MUTED)
        return
    if portrait:
        art = ImageOps.fit(art, (box.w, box.h), Image.Resampling.LANCZOS, centering=(0.5, 0.25))
        mask = Image.new("L", art.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, box.w, box.h), radius=10, fill=255)
        art.putalpha(mask)
    else:
        art.thumbnail((box.w, box.h), Image.Resampling.LANCZOS)
    ctx.image.alpha_composite(art, (box.x + (box.w - art.width) // 2, box.y + (box.h - art.height) // 2))
