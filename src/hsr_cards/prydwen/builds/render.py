"""Offline PIL build cards, with optional exact-source condition sheets.

The detailed card is a visual index into a reviewed JSON file, not a replacement
for its conditional advice. Numbered references lead to companion PNG pages
containing the original wording. No rankings, team slots or values are inferred.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .models import AssetRef, BuildCardData, ReviewStatus
from .nanoka import NanokaIndex

W, H = 1920, 1440
PACKAGE_ASSETS = Path(__file__).resolve().parents[2] / "assets"
FONT_DIR = Path("C:/Windows/Fonts")
EXTERNAL_FONTS = PACKAGE_ASSETS / "fonts"
INK = (246, 241, 233, 255)
MUTED = (201, 193, 189, 255)
DIM = (155, 151, 158, 255)
GOLD = (231, 199, 144, 255)
LINE = (161, 142, 112, 110)
PANEL = (10, 13, 26, 226)
ACCENTS = {
    "physical": (198, 198, 191), "fire": (255, 137, 122),
    "ice": (133, 220, 250), "lightning": (193, 146, 244),
    "wind": (132, 230, 188), "quantum": (155, 165, 255),
    "imaginary": (245, 217, 143),
}
# Verified against the supplied font's SVG/CSS mapping; these are glyphs,
# rather than arbitrary Unicode characters that may render as missing boxes.
HSR_GLYPHS = {"lightcone": "Q", "character": "K", "star": "b", "note": "9"}


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int


@dataclass
class RenderContext:
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
        return ImageDraw.Draw(self.image)

    def note(self, key: str, heading: str, text: str | None) -> str:
        text = " ".join((text or "").split())
        if self.exclude_extra or not text:
            return ""
        if not any(item["id"] == key for item in self.notes):
            self.notes.append({"id": key, "heading": heading, "text": text})
        return f"[{key}]"


@lru_cache(maxsize=48)
def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """Use the supplied game font when possible; never download a font."""
    if weight == "icon":
        candidates = [EXTERNAL_FONTS / "hsr-icon.ttf"]
    elif weight == "bold":
        candidates = [FONT_DIR / "segoeuib.ttf", FONT_DIR / "arialbd.ttf"]
    elif weight == "title":
        candidates = [FONT_DIR / "bahnschrift.ttf", FONT_DIR / "segoeuib.ttf"]
    elif weight == "source":
        candidates = [FONT_DIR / "segoeui.ttf", FONT_DIR / "arial.ttf"]
    else:
        game_font = EXTERNAL_FONTS / "optimized_global_web.woff2"
        if game_font.is_file():
            try:
                from fontTools.ttLib import TTFont
                font = TTFont(game_font)
                font.flavor = None
                data = io.BytesIO()
                font.save(data)
                data.seek(0)
                return ImageFont.truetype(data, size)
            except (ImportError, OSError, ValueError):
                pass
        candidates = [FONT_DIR / "segoeui.ttf", FONT_DIR / "arial.ttf"]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    # Pillow's bundled DejaVu font gives a readable cross-platform fallback.
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


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


def _background(data: BuildCardData, nanoka: NanokaIndex) -> RenderContext:
    accent = ACCENTS.get(data.character.element.casefold(), GOLD[:3])
    image = Image.new("RGBA", (W, H), (13, 16, 31, 255))
    draw = ImageDraw.Draw(image)
    for row in range(H):
        t = row / H
        draw.line((0, row, W, row), fill=(round(16 + 9 * t), round(20 - 3 * t), round(38 - 7 * t), 255))
    ctx = RenderContext(image, nanoka, accent)
    art = _load(ctx, data.character.drawcard)
    if art:
        # A soft echo of the splash ties the three columns together.
        echo = ImageOps.fit(art, (W, H), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(34))
        echo.putalpha(echo.getchannel("A").point(lambda p: round(p * .13)))
        image.alpha_composite(echo)
    glow = Image.new("RGBA", (W // 4, H // 4))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((110, -10, 360, 340), fill=(*accent, 34))
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(36)).resize((W, H)))
    return ctx


def _lightcones(ctx: RenderContext, data: BuildCardData) -> None:
    _panel(ctx, Box(32, 56, 592, 480))
    _title(ctx, "LIGHT CONES", 56, 80, 544, "lightcone")
    cones = data.light_cones[:3]
    if not cones:
        _text(ctx, "No recommendation available in cached source.", Box(60, 176, 528, 140), fill=MUTED)
        return
    for i, cone in enumerate(cones):
        x = 56 + i * 184
        ref = ctx.note(f"L{i + 1}", cone.name, cone.reason)
        _icon(ctx, cone.asset, Box(x + 16, 154, 142, 166))
        _text(ctx, cone.name, Box(x, 330, 174, 84), 22, weight="bold", align="center", max_lines=3)
        meta = f"S{cone.superimposition}" if cone.superimposition else "S?"
        if cone.score_text and "%" in cone.score_text:
            meta += " | " + cone.score_text
        elif cone.rank:
            meta += f" | #{cone.rank}"
        _text(ctx, meta, Box(x, 424, 174, 32), 23, fill=GOLD, align="center")
        weight = cone.weight.value.capitalize()
        _text(ctx, f"{weight} {ref}".strip(), Box(x, 462, 174, 28), 21, fill=MUTED, align="center")
        ctx.shown.append({"section": "light_cones", "name": cone.name})
    if len(data.light_cones) > 3:
        ctx.omitted.append(f"{len(data.light_cones) - 3} additional light-cone options")
    extra = f"  |  +{len(data.light_cones) - 3} more in JSON" if len(data.light_cones) > 3 else ""
    _text(ctx, "Source order" if ctx.exclude_extra else "Source order" + extra + "  |  [L] conditions", Box(58, 500, 540, 28), 20, fill=DIM)


def _member(ctx: RenderContext, name: str, asset: AssetRef | None, box: Box, *, size: int = 22) -> None:
    icon_w = min(82, box.w)
    _icon(ctx, asset, Box(box.x + (box.w - icon_w) // 2, box.y, icon_w, 98), portrait=True)
    _text(ctx, name, Box(box.x, box.y + 106, box.w, 62), size, align="center", max_lines=2)


def _editorial_group(ctx: RenderContext, team: Any, box: Box, index: int) -> None:
    _text(ctx, team.name + ("" if ctx.exclude_extra else f" [E{index + 1}]"), Box(box.x, box.y, box.w, 62), 26, weight="bold", fill=GOLD, max_lines=2)
    slots = team.slots
    if not slots:
        # Legacy JSON flattens alternative candidates. Never imply that an
        # arbitrary first four members are a valid four-character lineup.
        _text(ctx, "Candidates; source slot grouping unavailable", Box(box.x, box.y + 70, box.w, 58), 22, fill=MUTED)
        for i, member in enumerate(team.members[:4]):
            _member(ctx, member.name, member.asset, Box(box.x + i * 134, box.y + 132, 126, 162), size=20)
        ctx.omitted.append(f"{team.name}: legacy candidate grouping requires review")
        return
    cell_w = box.w // max(1, len(slots))
    for col, slot in enumerate(slots):
        x = box.x + col * cell_w
        _text(ctx, slot.role or f"Slot {col + 1}", Box(x, box.y + 64, cell_w - 6, 30), 20, fill=MUTED, align="center")
        for row, member in enumerate(slot.members[:2]):
            iy = box.y + 100 + row * 116
            _icon(ctx, member.asset, Box(x + (cell_w - 58) // 2, iy, 58, 70), portrait=True)
            _text(ctx, member.name, Box(x, iy + 74, cell_w - 6, 48), 18, align="center", max_lines=2)
            if row == 0 and len(slot.members) > 1:
                _text(ctx, "or", Box(x + cell_w - 26, iy + 44, 24, 22), 18, fill=DIM, align="center")
        if len(slot.members) > 2 and not ctx.exclude_extra:
            _text(ctx, f"+{len(slot.members) - 2}", Box(x + cell_w - 38, box.y + 224, 36, 24), 18, fill=GOLD, weight="bold")
            ctx.omitted.append(f"{team.name}, slot {col + 1}: {len(slot.members) - 2} more alternatives")


def _teams(ctx: RenderContext, data: BuildCardData) -> None:
    _panel(ctx, Box(32, 560, 592, 796))
    _title(ctx, "TEAMS & ALLIES", 56, 584, 544, "character")
    if data.editorial_teams:
        more = f" | +{len(data.editorial_teams) - 2} groups" if len(data.editorial_teams) > 2 else ""
        _text(ctx, "Choose one per source slot" + ("" if ctx.exclude_extra else more), Box(56, 652, 544, 28), 21, fill=DIM)
        for i, team in enumerate(data.editorial_teams[:2]):
            _editorial_group(ctx, team, Box(56, 696 + i * 322, 544, 302), i)
            names = {member.name for slot in team.slots for member in slot.members[:2]}
            notes = ([team.note] if team.note else []) + [synergy.note for synergy in data.synergies if names.intersection(synergy.characters)]
            ctx.note(f"E{i + 1}", team.name, "\n\n".join(notes) or team.name)
        if len(data.editorial_teams) > 2:
            ctx.omitted.append(f"{len(data.editorial_teams) - 2} additional editorial team groups")
        return
    more = f" (+{len(data.synergies) - 6} in JSON)" if len(data.synergies) > 6 else ""
    _text(ctx, "Synergy options, not a full team" + ("" if ctx.exclude_extra else more), Box(56, 652, 544, 58), 22, fill=DIM, max_lines=2)
    allies = data.synergies[:6]
    for i, ally in enumerate(allies):
        x, y = 56 + (i % 3) * 184, 720 + (i // 3) * 196
        ref = ctx.note(f"A{i + 1}", " / ".join(ally.characters), ally.note)
        # A grouped synergy keeps every source member represented, side by side.
        members = [(name, ally.character_assets[j] if j < len(ally.character_assets) else None) for j, name in enumerate(ally.characters)]
        shown = members[:4]
        for j, (_, asset) in enumerate(shown):
            if len(shown) > 3:
                width, height = 46, 44
                px = x + 36 + (j % 2) * 52
                py = y + (j // 2) * 48
            else:
                width = 78 if len(shown) == 1 else (70 if len(shown) == 2 else 52)
                height = 92 if len(shown) < 3 else 74
                px = x + (174 - len(shown) * width) // 2 + j * width
                py = y
            _icon(ctx, asset, Box(px, py, width - 4, height), portrait=True)
        group_name = " / ".join(ally.characters)
        if len(_wrap(group_name, _font(22), 174)) > 2:
            group_name = f"{len(ally.characters)} ally options"
        _text(ctx, group_name, Box(x, y + 102, 174, 58), 22, align="center", max_lines=2)
        if len(members) > 4:
            ctx.omitted.append(f"{ref}: {len(members) - 4} additional grouped ally options")
        _text(ctx, ref, Box(x, y + 164, 174, 26), 20, fill=GOLD, align="center")
    if len(data.synergies) > 6:
        ctx.omitted.append(f"{len(data.synergies) - 6} additional synergy entries")
    mode = next((mode for mode in data.teams if mode.variants), None)
    if mode:
        team = mode.variants[0]
        _rule(ctx, 56, 1124, 544)
        _text(ctx, mode.label + " • usage sample", Box(56, 1140, 544, 34), 24, weight="bold", fill=GOLD)
        for i, name in enumerate(team.characters[:4]):
            asset = team.character_assets[i] if i < len(team.character_assets) else None
            _member(ctx, name, asset, Box(56 + i * 136, 1186, 128, 150), size=19)
        ctx.shown.append({"section": "usage_team", "name": mode.label})
    elif not allies:
        _text(ctx, "No team or synergy information available.", Box(56, 736, 544, 140), fill=MUTED)


def _center(ctx: RenderContext, data: BuildCardData) -> None:
    hero = _load(ctx, data.character.drawcard)
    if hero:
        crop = ImageOps.fit(hero, (580, 846), Image.Resampling.LANCZOS, centering=(.5, .37))
        # Fade only the base of the art, so its edges merge into the canvas.
        alpha = crop.getchannel("A")
        mask = Image.new("L", crop.size, 255)
        md = ImageDraw.Draw(mask)
        for y in range(706, 846):
            md.line((0, y, 580, y), fill=round(255 * (846 - y) / 140))
        from PIL import ImageChops
        crop.putalpha(ImageChops.multiply(alpha, mask))
        ctx.image.alpha_composite(crop, (648, 56))
    else:
        _text(ctx, "Character artwork unavailable", Box(678, 380, 520, 150), 34, fill=DIM, align="center")
    _text(ctx, data.character.name.upper(), Box(656, 874, 564, 124), 49, weight="title", align="center", max_lines=2)
    _icon(ctx, data.character.element_icon, Box(684, 1000, 42, 42))
    _icon(ctx, data.character.path_icon, Box(1160, 1000, 42, 42))
    if getattr(data, "build_name", None):
        _text(ctx, data.build_name, Box(678, 956, 520, 32), 23, fill=MUTED, align="center")
    _text(ctx, f"{data.character.element} / {data.character.path}", Box(730, 1007, 424, 36), 25, fill=(*ctx.accent, 255), align="center")
    _text(ctx, "BASE STATS • LEVEL 80", Box(680, 1060, 516, 30), 21, fill=DIM, align="center")
    for i, (label, value) in enumerate((("HP", data.stats.hp), ("ATK", data.stats.atk), ("DEF", data.stats.defence), ("SPD", data.stats.speed))):
        x = 666 + (i % 2) * 282
        y = 1102 + (i // 2) * 52
        _icon(ctx, ctx.nanoka.stat_asset(label), Box(x, y, 34, 34))
        _text(ctx, label, Box(x + 44, y + 4, 82, 34), 22, fill=MUTED)
        _text(ctx, f"{value:,}" if value is not None else "?", Box(x + 122, y, 142, 42), 32, weight="bold")
    _rule(ctx, 666, 1214, 544)
    _text(ctx, "TRACE PRIORITY" if ctx.exclude_extra else "TRACE PRIORITY [P1]", Box(666, 1234, 544, 30), 22, weight="bold", fill=GOLD)
    trace = data.trace_priority
    steps = trace.skill_steps
    if not steps and trace.skills:
        from .models import TraceStep
        labels = [part.strip() for part in re.split(r"(?:>=|<=|>|<|=)", trace.skills) if part.strip()]
        steps = [TraceStep(label=label, asset=ctx.nanoka.skill_asset(data.character.nanoka_id, label)) for label in labels]
    if not ctx.exclude_extra and steps and (len(steps) > 6 or re.search(r"\bor\b|focus|if |when ", trace.skills or "", re.I)):
        _text(ctx, "Conditional priorities; see [P1]", Box(666, 1286, 544, 64), 26, fill=MUTED, max_lines=2)
        ctx.omitted.append("Conditional trace priority shown only on [P1] condition sheet")
    elif steps:
        cell = 544 // min(6, len(steps))
        ops = trace.skill_operators or re.findall(r">=|<=|>|<|=", trace.skills or "")
        for i, step in enumerate(steps[:6]):
            x = 666 + i * cell
            _icon(ctx, step.asset, Box(x + (cell - 48) // 2, 1280, 48, 48))
            label = step.label.replace("Memosprite", "Memo")
            _text(ctx, label, Box(x, 1328, cell - 4, 48), 18, align="center", max_lines=2)
            if i < len(steps[:6]) - 1:
                _text(ctx, ops[i] if i < len(ops) else "?", Box(x + cell - 12, 1290, 40, 30), 22, fill=GOLD)
    else:
        _text(ctx, "Not available in source", Box(666, 1292, 544, 60), 24, fill=MUTED)
    ctx.note("P1", "Trace priority", trace.raw_text or trace.skills)


def _relic_display(candidates: list[tuple[Any, Any]], limit: int = 3) -> list[tuple[Any, Any]]:
    """Keep a 2+2 combination together, including when a tile limit is reached."""
    result: list[tuple[Any, Any]] = []
    seen: set[str] = set()
    for group, relic in candidates:
        key = relic.combination_id
        if key:
            if key in seen:
                continue
            seen.add(key)
            block = [(g, r) for g, r in candidates if r.combination_id == key]
            # An incomplete pair must never look like a standalone recommendation.
            if len(block) < 2:
                continue
        else:
            block = [(group, relic)]
        if len(result) + len(block) <= limit:
            result.extend(block)
    return result


def _relics(ctx: RenderContext, data: BuildCardData) -> None:
    _title(ctx, "RELICS & STATS", 1276, 80, 588)
    y = 160
    ordinal = 0
    for slot, label in (("cavern", "CAVERN RELICS"), ("planar", "PLANAR ORNAMENTS")):
        candidates = [(group, relic) for group in data.relic_sets if group.slot == slot for relic in group.recommendations]
        selected = _relic_display(candidates)
        extra = len(candidates) - len(selected)
        heading = label + (f"  +{extra} in JSON" if extra and not ctx.exclude_extra else "")
        _text(ctx, heading, Box(1276, y, 588, 34), 23, weight="bold", fill=MUTED)
        y += 38
        for i, (group, relic) in enumerate(selected):
            x = 1276 + i * 200
            ordinal += 1
            marker = ctx.note(f"R{ordinal}", f"{relic.pieces or '?'}-piece {relic.name}", relic.reason)
            _icon(ctx, relic.asset, Box(x + 49, y, 88, 74))
            _text(ctx, relic.name, Box(x, y + 78, 186, 78), 20, weight="bold", align="center", max_lines=3)
            tags = f"{relic.pieces or '?'}P"
            if relic.combination_id:
                tags += " pair"
                if i and selected[i - 1][1].combination_id == relic.combination_id:
                    _text(ctx, "+", Box(x - 24, y + 20, 40, 36), 30, fill=GOLD)
            if relic.flex and not relic.combination_id:
                tags = "2P + Flex2P"
            elif relic.score_text and "%" in relic.score_text:
                tags += f" {relic.score_text}"
            _text(ctx, f"{tags} {marker}", Box(x, y + 156, 186, 30), 19 if relic.flex else 20, fill=GOLD, align="center")
            weight = "Specialist" if "specialist" in group.heading.casefold() else group.weight.value.capitalize()
            weight = "Flex options" if relic.flex else weight
            _text(ctx, weight, Box(x, y + 187, 186, 24), 19, fill=DIM, align="center")
            ctx.shown.append({"section": slot, "name": relic.name})
        if extra:
            ctx.omitted.append(f"{extra} additional {slot} relic recommendations")
        if not selected:
            _text(ctx, "Not available in cached source", Box(1276, y + 46, 588, 60), fill=DIM)
        y += 210


def _choice_text(choice: Any) -> str:
    if not choice.values:
        return choice.raw_text
    parts = [choice.values[0]]
    for i, value in enumerate(choice.values[1:]):
        parts.extend([choice.operators[i] if i < len(choice.operators) else "/", value])
    return " ".join(parts)


def _stats(ctx: RenderContext, data: BuildCardData) -> None:
    _rule(ctx, 1276, 650, 588)
    _text(ctx, "MAIN STATS", Box(1276, 670, 588, 34), 28, weight="title", fill=GOLD)
    for i, choice in enumerate(data.main_stats[:4]):
        x, y = 1276 + (i % 2) * 302, 718 + (i // 2) * 116
        ref = choice.icons[0] if choice.icons else ctx.nanoka.stat_asset(choice.values[0] if choice.values else "")
        offset = 46 if ref else 0
        if ref:
            _icon(ctx, ref, Box(x, y + 26, 38, 38))
        _text(ctx, choice.slot + ("" if ctx.exclude_extra else f" [M{i + 1}]"), Box(x + offset, y, 284 - offset, 28), 20, fill=DIM)
        value = _choice_text(choice)
        if not ctx.exclude_extra and len(_wrap(value, _font(24), 284 - offset)) > 2:
            value = f"See stats [M{i + 1}]"
        _text(ctx, value, Box(x + offset, y + 34, 284 - offset, 66), 24, max_lines=2)
        ctx.note(f"M{i + 1}", "Main stat - " + choice.slot, choice.raw_text)
    if len(data.main_stats) > 4:
        ctx.omitted.append(f"{len(data.main_stats) - 4} more main stat entries on sheets")
        for i, choice in enumerate(data.main_stats[4:], start=5):
            ctx.note(f"M{i}", "Main stat - " + choice.slot, choice.raw_text)
    _rule(ctx, 1276, 948, 588)
    _text(ctx, "SUBSTAT PRIORITY", Box(1276, 968, 588, 34), 28, weight="title", fill=GOLD)
    raw = data.substats_raw or " > ".join(data.substats)
    if raw:
        # Keep the exact priority and breakpoint conditions together.
        ctx.note("S1", "Substat priority", raw)
        lines = _wrap(raw, _font(24), 588)
        if ctx.exclude_extra or len(lines) <= 3:
            _text(ctx, raw, Box(1276, 1012, 588, 90), 24, max_lines=3)
        else:
            _text(ctx, "Conditional priority — see [S1]", Box(1276, 1012, 588, 90), 24, fill=MUTED)
    else:
        _text(ctx, "Not available in source", Box(1276, 1012, 588, 58), 24, fill=DIM)
    _rule(ctx, 1276, 1110, 588)
    goals_label = "STAT GOALS [T0]" if data.stat_target_notes and not ctx.exclude_extra else "STAT GOALS"
    if len(data.stat_targets) > 6:
        if not ctx.exclude_extra:
            goals_label += f" (+{len(data.stat_targets) - 6} on sheets)"
        ctx.omitted.append(f"{len(data.stat_targets) - 6} further stat targets on condition sheets")
        for i, target in enumerate(data.stat_targets[6:], start=7):
            ctx.note(f"T{i}", "Stat target - " + target.stat, target.target + "\n" + "\n".join(target.notes))
    _text(ctx, goals_label, Box(1276, 1130, 588, 34), 28, weight="title", fill=GOLD)
    for i, target in enumerate(data.stat_targets[:6]):
        x, y = 1276 + (i % 3) * 200, 1178 + (i // 3) * 82
        details = target.target
        extra = [note for note in target.notes if note not in details]
        if extra:
            details += "\n" + "\n".join(extra)
        marker = ctx.note(f"T{i + 1}", "Stat target — " + target.stat, details)
        ref = target.icon or ctx.nanoka.stat_asset(target.stat)
        if ref:
            _icon(ctx, ref, Box(x, y, 28, 28))
        short_labels = {"energy regen rate": "Energy regen", "energy regeneration rate": "Energy regen",
                        "effect hit rate": "Effect hit", "effect resistance": "Effect RES", "effect hit rating": "Effect hit"}
        stat_key = target.stat.casefold()
        label = short_labels.get(stat_key, target.stat)
        if stat_key in {"energy regen", "energy regeneration"}:
            label = "Energy regen"
        if "(" in label:
            label = label.split("(", 1)[0].strip() + " " + marker
        unknown_label = _font(20).getlength(label) > (154 if ref else 188)
        if unknown_label and not ctx.exclude_extra:
            label = "Target " + marker
        _text(ctx, label, Box(x + (34 if ref else 0), y, 154 if ref else 188, 28), 20, fill=DIM)
        text = target.target + (" " + marker if target.notes else "")
        if unknown_label and not ctx.exclude_extra:
            text = f"See target {marker}"
        # Measure the final label with its actual bold font. A marker must
        # never cause a numeric range or the accompanying condition to clip.
        if not ctx.exclude_extra and _font(23, "bold").getlength(text) > 188:
            text = f"See target {marker}"
        _text(ctx, text, Box(x, y + 34, 188, 34), 23, weight="bold")
    if not data.stat_targets:
        _text(ctx, "No stat targets available", Box(1276, 1190, 588, 60), fill=DIM)
    ctx.note("T0", "Additional stat target notes", "\n".join(data.stat_target_notes))


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


def _footer(ctx: RenderContext, data: BuildCardData) -> None:
    status = "REVIEWED" if data.review.status == ReviewStatus.APPROVED else "DRAFT • CHECK BEFORE SHARING"
    _text(ctx, "HONKAI: STAR RAIL / BUILD GUIDE", Box(34, 20, 1100, 28), 20, fill=DIM)
    _text(ctx, status, Box(1150, 18, 738, 30), 22, fill=GOLD, weight="bold", align="right")
    _rule(ctx, 32, 1382, 1856)
    _text(ctx, "PRYDWEN.GG  |  " + _dates(data), Box(34, 1397, 1360, 30), 20, fill=MUTED)
    note_label = "[IDs] + [N1] condition sheets" if any(note["id"] == "N1" for note in ctx.notes) else "[IDs] condition sheets"
    _text(ctx, "" if ctx.exclude_extra else note_label, Box(1400, 1397, 488, 30), 20, fill=GOLD, align="right")


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


def render_card(
    data: dict[str, Any] | BuildCardData, out: Path, *, nanoka: NanokaIndex,
    exclude_extra: bool = True, report_dir: Path | None = None,
) -> Path:
    """Render a clean summary, or a detailed summary with condition pages.

    Detailed outputs use `<name>.detailed.png`. Source models are never changed.
    `report_dir` keeps working reports separate from published images.
    """
    model = data if isinstance(data, BuildCardData) else BuildCardData.model_validate(data)
    out = Path(out)
    stem = out.stem.removesuffix(".detailed")
    out = out.with_name(stem + ("" if exclude_extra else ".detailed") + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    ctx = _background(model, nanoka)
    ctx.exclude_extra = exclude_extra
    _panel(ctx, Box(1252, 56, 636, 1300))
    _center(ctx, model)
    _lightcones(ctx, model)
    _teams(ctx, model)
    _relics(ctx, model)
    _stats(ctx, model)
    general = "\n".join([*model.notes, *model.review_notes, *model.team_comments])
    ctx.note("N1", "General build and team notes", general)
    _footer(ctx, model)
    ctx.image.convert("RGB").save(out, "PNG", optimize=True)
    # Only files emitted by this renderer for this exact stem may be removed.
    # A shorter note set must not leave stale advice beside the new card.
    stale_pattern = re.compile(re.escape(out.stem) + r"\.conditions-\d+\.png$")
    for sibling in out.parent.iterdir():
        if sibling.is_file() and stale_pattern.fullmatch(sibling.name):
            sibling.unlink()
    sheets = [] if exclude_extra else _notes_pages(ctx, model, out)
    manifest = {
        "schema_version": 1, "character": model.character.slug, "exclude_extra": exclude_extra,
        "size": [W, H], "review_status": model.review.status.value,
        "source": str(model.character.source_url),
        "source_html_sha256": model.source_meta.html_sha256 if model.source_meta else None,
        "outputs": [out.name, *[path.name for path in sheets]],
        "condition_sheets": [path.name for path in sheets],
        "conditions": ctx.notes, "shown": ctx.shown,
        "omitted_options": ctx.omitted,
        "missing_assets": sorted(ctx.missing_assets),
        "clipped_text": list(dict.fromkeys(ctx.clipped_text)),
        "requires_condition_sheets": bool(sheets),
    }
    report_root = Path(report_dir) if report_dir is not None else out.parent
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / (out.stem + ".render.json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
