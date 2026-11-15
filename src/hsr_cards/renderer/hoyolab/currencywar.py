"""Currency Wars (``grid_fight``) run card.

One image per archived run, sized 720 px wide so it fits Telegram's photo
limits. The palette and layout follow the in-game / HoYoLAB battle record
view: a violet header band, a stat strip carrying the run rank, compact unit
tiles with rarity stars and equipment, bond/plot/investment chips, and a
bar-based damage chart.

Character elements come from the read-only Nanoka cache when available (the
data files ship next to the package); nothing here writes to or calls the
Nanoka API.
"""

from __future__ import annotations

import asyncio
import json
import math
from io import BytesIO
from pathlib import Path
from typing import Optional

import aiohttp
from PIL import Image, ImageDraw, ImageFilter

from ...models.currencywar import (
    CurrencyWarData,
    CurrencyWarRole,
    CurrencyWarRun,
)
from ...utils.errors import HSR_Error
from ...utils.hsrfonts import HSRFonts

_ASSETS = Path(__file__).parent.parent.parent / "assets"
_COIN = _ASSETS / "general" / "cw_coin.png"
_SSS = _ASSETS / "general" / "cw_sss.png"

W, PAD = 720, 20
GAP = 12
CORNER = 8
INNER = W - PAD * 2

BG_BODY = (35, 35, 78, 255)
BG_PANEL = (27, 27, 64, 255)
HEADER_TOP = (94, 80, 214, 255)
HEADER_BOTTOM = (64, 54, 171, 255)
STAT_TOP = (46, 43, 126, 255)
STAT_BOTTOM = (34, 32, 92, 255)
CHIP = (55, 52, 145, 255)
CHIP_PLOT = (48, 46, 128, 255)
BORDER = (72, 67, 146, 255)
WHITE = (255, 255, 255, 255)
TEXT = (231, 230, 249, 255)
LABEL = (206, 206, 238, 255)
MUTED = (164, 166, 204, 255)
GOLD = (255, 205, 96, 255)
CREAM = (255, 232, 166, 255)
BAR = (255, 197, 82, 255)
BAR_TRAIT = (206, 172, 255, 255)
HP_PINK = (255, 143, 172, 255)

TIER_COLORS = {
    0: (150, 148, 182, 255),
    1: (110, 212, 152, 255),
    2: (104, 170, 250, 255),
    3: (186, 132, 244, 255),
    4: (246, 188, 86, 255),
    5: (238, 124, 180, 255),
}

ELEMENT_COLORS = {
    "physical": (205, 205, 205),
    "fire": (244, 92, 86),
    "ice": (112, 200, 244),
    "lightning": (190, 128, 255),
    "wind": (106, 218, 162),
    "quantum": (126, 104, 238),
    "imaginary": (246, 206, 92),
    "thunder": (190, 128, 255),
}

def _cache_roots() -> tuple[Path, Path]:
    """Resolve Nanoka cache locations only when a Currency Wars asset is needed."""
    return (
        Path(__file__).resolve().parents[4] / ".nanoka_cache",
        Path.cwd() / ".nanoka_cache",
    )


def _font(size: int, weight: str = "medium"):
    return HSRFonts.get_font(size, weight)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "...", font=font) > max_w:
        text = text[:-1]
    return (text.rstrip() + "...") if text else "..."


def _compact(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.45
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=fill)


def _star_row(draw: ImageDraw.ImageDraw, x: float, y: float, count: int, r: float = 4) -> None:
    step = r * 2 + 1.5
    for i in range(count):
        _star(draw, x + r + i * step, y + r, r, GOLD)


def _heart(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float, fill) -> None:
    r = size * 0.28
    draw.ellipse((cx - size / 2, cy - size / 2, cx - size / 2 + 2 * r, cy - size / 2 + 2 * r), fill=fill)
    draw.ellipse((cx + size / 2 - 2 * r, cy - size / 2, cx + size / 2, cy - size / 2 + 2 * r), fill=fill)
    draw.polygon(
        [(cx - size / 2, cy - size * 0.08), (cx + size / 2, cy - size * 0.08), (cx, cy + size / 2)],
        fill=fill,
    )


def _diamond(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float, fill, outline=None) -> None:
    pts = [(cx, cy - size / 2), (cx + size / 2, cy), (cx, cy + size / 2), (cx - size / 2, cy)]
    draw.polygon(pts, fill=fill, outline=outline)


def _quality_color(quality: str) -> tuple:
    try:
        return TIER_COLORS.get(int(quality), MUTED)
    except (TypeError, ValueError):
        return MUTED


def _round_image(img: Image.Image, size: int, radius: Optional[int] = None) -> Image.Image:
    radius = size // 6 if radius is None else radius
    mask = Image.new("L", (size * 3, size * 3), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size * 3 - 1, size * 3 - 1), radius=max(1, radius) * 3, fill=255
    )
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img.convert("RGBA").resize((size, size), Image.LANCZOS), (0, 0), mask)
    return out


def _cover(img: Image.Image, size: tuple[int, int], top_bias: float = 0.08) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = img.convert("RGBA").resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = int((new_h - target_h) * top_bias)
    return resized.crop((left, top, left + target_w, top + target_h))


def _ringed(img: Image.Image, size: int, color, width: int = 2) -> Image.Image:
    outer = size + width * 2
    base = Image.new("RGBA", (outer, outer), (0, 0, 0, 0))
    ImageDraw.Draw(base).ellipse((0, 0, outer - 1, outer - 1), fill=color)
    avatar = _round_image(img, size, radius=size // 2)
    base.paste(avatar, (width, width), avatar)
    return base


def _section(draw: ImageDraw.ImageDraw, title: str, y: int, x: int = PAD, width: int = INNER) -> int:
    draw.text((x + 2, y), title, font=_font(14, "bold"), fill=WHITE)
    draw.line((x + 2, y + 20, x + width, y + 20), fill=(64, 60, 128, 120), width=1)
    return y + 28


def _gamut(value: float) -> int:
    return max(0, min(255, int(value)))


def _vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    band = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    for row in range(size[1]):
        t = row / max(1, size[1] - 1)
        draw.line(
            (0, row, size[0], row),
            fill=tuple(_gamut(top[i] * (1 - t) + bottom[i] * t) for i in range(4)),
        )
    return band


def _element_map() -> dict[str, str]:
    """Read character element names from the Nanoka cache (read-only)."""
    mapping: dict[str, str] = {}
    for root in _cache_roots():
        if not root.is_dir():
            continue
        for version in sorted(root.iterdir(), reverse=True):
            char_dir = version / "en" / "data" / "character"
            if not char_dir.is_dir():
                continue
            for path in char_dir.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                avatar = str(payload.get("chara_info", {}).get("avatar_id") or path.stem)
                damage = str(payload.get("damage_type") or "").lower()
                if damage:
                    mapping.setdefault(avatar, damage)
            return mapping
    return mapping


class CurrencyWarResult:
    """A rendered run plus navigation across the run list.

    Runs are ordered newest-first as the API returns them: ``next()`` walks to
    older runs and ``prev()`` to newer ones.
    """

    def __init__(self, image: Image.Image, current: int, total: int,
                 data: Optional[CurrencyWarData] = None) -> None:
        self.image = image
        self.current = current
        self.total = total
        self.all = list(range(total))
        self.data = data

    @property
    def has_next(self) -> bool:
        return self.current + 1 < self.total

    @property
    def has_prev(self) -> bool:
        return self.current > 0

    def next(self, index: Optional[int] = None) -> Optional[int]:
        base = self.current if index is None else index
        return base + 1 if 0 <= base + 1 < self.total else None

    def prev(self, index: Optional[int] = None) -> Optional[int]:
        base = self.current if index is None else index
        return base - 1 if 0 <= base - 1 < self.total else None

    def save(self, path) -> None:
        self.image.save(path)


class CurrencyWarRenderer:
    """Renders Currency Wars archive runs (one image per run)."""

    def __init__(self) -> None:
        self.session: Optional[aiohttp.ClientSession] = None
        self._icons: dict[str, Image.Image] = {}
        self._elements: Optional[dict[str, str]] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *_):
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def _icon(self, url: str) -> Optional[Image.Image]:
        if not url:
            return None
        if url in self._icons:
            return self._icons[url]
        if self.session is None:
            self.session = aiohttp.ClientSession()
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
            img = Image.open(BytesIO(data)).convert("RGBA")
            self._icons[url] = img
            return img
        except Exception:
            return None

    async def _load_icons(self, urls: list[str]) -> dict[str, Optional[Image.Image]]:
        unique = list(dict.fromkeys(u for u in urls if u))
        results = await asyncio.gather(*(self._icon(u) for u in unique))
        return dict(zip(unique, results))

    async def render_currency_war(self, data: CurrencyWarData | dict, index: int = 0) -> CurrencyWarResult:
        if isinstance(data, dict):
            data = CurrencyWarData.model_validate(data)
        runs = data.grid_fight_archive_list
        if not runs:
            raise HSR_Error("No Currency Wars runs available")
        if not -len(runs) <= index < len(runs):
            raise HSR_Error(f"Run index {index} out of range (0-{len(runs) - 1})")
        index = index if index >= 0 else len(runs) + index
        image = await self.render_run(runs[index], index, len(runs))
        return CurrencyWarResult(image, index, len(runs), data)

    async def render_run(self, run: CurrencyWarRun, index: int = 0, total: int = 1) -> Image.Image:
        lineup = run.lineup
        roles = list(lineup.front_roles) + list(lineup.back_roles)
        urls = [r.icon for r in roles]
        urls += [e.icon for r in roles for e in r.equip_list]
        urls += [t.icon for t in lineup.trait_list]
        urls += [p.icon for p in lineup.portal_list]
        urls += [a.icon for a in lineup.augment_list]
        urls += [s.icon for s in lineup.spot_light_list]
        urls += [s.role_icon or "" for s in lineup.spot_light_list]
        urls += [run.brief.division.icon]
        icons = await self._load_icons(urls)

        if self._elements is None:
            self._elements = _element_map()

        coin = Image.open(_COIN).convert("RGBA")
        sss = Image.open(_SSS).convert("RGBA")
        return self._compose(run, index, total, icons, coin, sss).convert("RGB")

    def _compose(self, run, index, total, icons, coin, sss) -> Image.Image:
        layer = Image.new("RGBA", (W, 3200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        y = self._header(layer, draw, run.brief, index, icons)
        y += GAP
        y = self._stats(layer, draw, run.brief, coin, sss, y)
        y += GAP
        y = self._units(layer, draw, run.lineup, icons, y)
        y += GAP
        y = self._bonds(layer, draw, run.lineup, icons, y)
        y += GAP
        y = self._plot(layer, draw, run.lineup, icons, y)
        y += GAP
        y = self._invest(layer, draw, run.lineup, icons, y)
        y += GAP
        y = self._damage(layer, draw, run.lineup, icons, y)

        footer_h = 24
        final_h = y + PAD + footer_h
        canvas = Image.new("RGBA", (W, final_h), BG_BODY)
        self._background(canvas)
        canvas.alpha_composite(layer.crop((0, 0, W, final_h)))

        draw = ImageDraw.Draw(canvas)
        footer = _font(10, "medium")
        draw.text((PAD, final_h - 18), "Currency Wars  |  HoYoLAB battle records", font=footer, fill=MUTED)
        counter = f"{index + 1} / {total}"
        draw.text((W - PAD - draw.textlength(counter, font=footer), final_h - 18), counter, font=footer, fill=MUTED)
        return canvas

    def _background(self, canvas: Image.Image) -> None:
        draw = ImageDraw.Draw(canvas)
        for row in range(canvas.height):
            t = row / max(1, canvas.height)
            draw.line((0, row, W, row), fill=tuple(_gamut(BG_BODY[i] * (1 - t) + (16, 16, 40, 255)[i] * t) for i in range(4)))

        glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse((-220, -300, 520, 360), fill=(110, 84, 240, 34))
        g.ellipse((W - 300, 240, W + 260, 800), fill=(255, 180, 80, 14))
        canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(96)))

    # -- header -----------------------------------------------------------

    def _header(self, canvas, draw, brief, index, icons) -> int:
        height = 72
        x0, x1 = PAD, W - PAD
        band = _vertical_gradient((x1 - x0, height), HEADER_TOP, HEADER_BOTTOM)

        flare = Image.new("RGBA", band.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(flare)
        fd.ellipse((-120, -120, 260, 220), fill=(190, 176, 255, 34))
        fd.ellipse((band.width - 180, -60, band.width + 160, 220), fill=(150, 132, 255, 22))
        band.alpha_composite(flare.filter(ImageFilter.GaussianBlur(18)))

        mask = Image.new("L", band.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, band.width - 1, height - 1), radius=CORNER, fill=255)
        canvas.paste(band, (x0, 0), mask)

        div_icon = icons.get(brief.division.icon)
        if div_icon is not None:
            canvas.alpha_composite(_round_image(div_icon, 26, radius=5), (x0 + 10, 9))
            tx = x0 + 44
        else:
            tx = x0 + 12

        f_div = _font(18, "bold")
        draw.text((tx, 10), brief.division.name_with_num, font=f_div, fill=WHITE)
        chip_x = tx + draw.textlength(brief.division.name_with_num, font=f_div) + 10

        f_tag = _font(11, "bold")
        tag = "Standard Gambit"
        tw = int(draw.textlength(tag, font=f_tag)) + 30
        draw.rounded_rectangle((chip_x, 12, chip_x + tw, 36), radius=4, fill=(26, 23, 74, 220), outline=(150, 132, 240, 255))
        _diamond(draw, chip_x + 13, 24, 11, (206, 192, 255, 255))
        _diamond(draw, chip_x + 13, 24, 5, (66, 54, 158, 255))
        draw.text((chip_x + 23, 24), tag, font=f_tag, fill=(236, 230, 255, 255), anchor="lm")

        draw.text((x0 + 12, 44), brief.archive_time, font=_font(11, "medium"), fill=(226, 220, 255, 255))
        return height

    def _stats(self, canvas, draw, brief, coin, sss, y) -> int:
        height = 88
        x0, x1 = PAD, W - PAD
        panel = _vertical_gradient((x1 - x0, height), STAT_TOP, STAT_BOTTOM)
        mask = Image.new("L", panel.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel.width - 1, height - 1), radius=CORNER, fill=255)
        canvas.paste(panel, (x0, y), mask)

        rank = brief.archive_rank.replace("GridFightArchiveRank", "").upper() or "?"
        rank_col = 106
        if rank == "SSS":
            emblem = sss.resize((72, 72), Image.LANCZOS)
        else:
            emblem = Image.new("RGBA", (78, 78), (0, 0, 0, 0))
            ed = ImageDraw.Draw(emblem)
            _diamond(ed, 39, 39, 58, (64, 54, 134, 255), outline=(150, 132, 240, 255))
            ed.text((39, 39), rank, font=_font(24 if len(rank) < 2 else 20, "bold"), fill=GOLD, anchor="mm")
        canvas.alpha_composite(emblem, (x0 + (rank_col - emblem.width) // 2, y + (height - emblem.height) // 2))
        draw.line((x0 + rank_col, y + 16, x0 + rank_col, y + height - 16), fill=(78, 70, 156, 255), width=1)

        w = (INNER - rank_col - 6) // 3
        f_label = _font(13, "bold")
        f_val = _font(26, "bold")
        for i, (label, kind, value) in enumerate(
            (("Squad HP", "hp", str(brief.remain_hp)),
             ("Total Currency", "coin", str(brief.total_coin)),
             ("Lineup Value", "coin", str(brief.lineup_coin)))
        ):
            cx = x0 + rank_col + 16 + i * w
            draw.text((cx, y + 13), label, font=f_label, fill=LABEL)
            if kind == "coin":
                canvas.alpha_composite(coin.resize((20, 20), Image.LANCZOS), (cx, y + 41))
            else:
                _heart(draw, cx + 10, y + 51, 18, HP_PINK)
            draw.text((cx + 27, y + 39), value, font=f_val, fill=WHITE)
        return y + height

    # -- units ------------------------------------------------------------

    def _units(self, canvas, draw, lineup, icons, y) -> int:
        half = (INNER - GAP) // 2
        draw.text((PAD, y), "On-Field", font=_font(14, "bold"), fill=WHITE)
        draw.text((PAD + half + GAP, y), "Off-Field", font=_font(14, "bold"), fill=WHITE)
        y += 24
        left_end = self._unit_grid(canvas, draw, lineup.front_roles, icons, PAD, y, half)
        right_end = self._unit_grid(canvas, draw, lineup.back_roles, icons, PAD + half + GAP, y, half)
        return max(left_end, right_end)

    def _unit_grid(self, canvas, draw, roles: list[CurrencyWarRole], icons, x, y, width) -> int:
        if not roles:
            draw.text((x, y + 6), "None", font=_font(12, "medium"), fill=MUTED)
            return y + 30

        count = len(roles)
        per_row = 6 if count > 4 else count
        gap = 6
        cell_w = min(72, (width - (per_row - 1) * gap) // per_row)
        cell_h = round(cell_w * 1.18)
        pitch = cell_h + 30

        for i, role in enumerate(roles):
            col = i % per_row
            row = i // per_row
            self._unit_cell(canvas, draw, role, icons, x + col * (cell_w + gap), y + row * pitch, cell_w, cell_h)
        rows = (count + per_row - 1) // per_row
        return y + (rows - 1) * pitch + cell_h + 18

    def _element_color(self, avatar_id: str) -> Optional[tuple]:
        if not self._elements:
            return None
        element = self._elements.get(str(avatar_id))
        if not element:
            return None
        return ELEMENT_COLORS.get(element)

    def _unit_cell(self, canvas, draw, role: CurrencyWarRole, icons, x, y, w, h) -> None:
        draw.rounded_rectangle((x, y, x + w - 1, y + h), radius=5, fill=BG_PANEL, outline=BORDER, width=1)
        icon = icons.get(role.icon)
        if icon is None:
            art = Image.new("RGBA", (w - 4, h - 4), (46, 44, 92, 255))
        else:
            art = _cover(icon, (w - 4, h - 4))

        element = self._element_color(role.avatar_id)
        if element is not None:
            draw.rounded_rectangle((x, y, x + w - 1, y + h), radius=5, outline=element + (255,), width=2)
        canvas.alpha_composite(_round_image(art, w - 4, radius=4), (x + 2, y + 2))

        if role.is_trial:
            f_tag = _font(9, "bold")
            label = "Trial"
            tw = int(draw.textlength(label, font=f_tag)) + 8
            draw.rounded_rectangle((x + 3, y + 3, x + 3 + tw, y + 16), radius=2, fill=(220, 55, 75, 255))
            draw.text((x + 7, y + 5), label, font=f_tag, fill=(255, 255, 255, 255))
        elif role.is_upgrade:
            draw.rounded_rectangle((x + w - 13, y + 3, x + w - 3, y + 13), radius=2, fill=(28, 24, 66, 220))
            draw.text((x + w - 8, y + 8), "+", font=_font(11, "bold"), fill=GOLD, anchor="mm")

        stars = int(role.star or 0)
        if stars:
            r = max(2.6, w * 0.05)
            total = stars * (r * 2 + 1.5)
            _star_row(draw, x + (w - total) / 2, y + h - 10, stars, r=r)

        equips = role.equip_list[:3]
        size = 15
        for i, equip in enumerate(equips):
            ex = x + i * (size + 2)
            ey = y + h + 4
            draw.rounded_rectangle((ex, ey, ex + size, ey + size), radius=3, fill=(44, 41, 100, 255), outline=(86, 80, 166, 255), width=1)
            e_icon = icons.get(equip.icon)
            if e_icon is not None:
                canvas.alpha_composite(_round_image(e_icon, size - 2, radius=2), (ex + 1, ey + 1))

    # -- chips ------------------------------------------------------------

    def _icon_badge(self, draw, icon_x, icon_y, icon_size, value, color, align="right") -> None:
        if value in (None, ""):
            return
        text = str(value)
        font = _font(11, "bold")
        bx = icon_x + (6 if align == "left" else icon_size - 6)
        by = icon_y + icon_size - 6
        w = max(18, int(draw.textlength(text, font=font)) + 11)
        box = (bx - w // 2, by - 9, bx + w // 2, by + 9)
        if w <= 18:
            draw.ellipse(box, fill=(18, 17, 42, 255), outline=color, width=1)
        else:
            draw.rounded_rectangle(box, radius=9, fill=(18, 17, 42, 255), outline=color, width=1)
        draw.text((bx, by), text, font=font, fill=(250, 249, 255, 255), anchor="mm")

    def _chip(self, canvas, draw, x, y, width, icon, label, *, badge="", accent=GOLD, height=32) -> int:
        f = _font(13, "medium")
        icon_size = height - 8

        label = _fit(draw, label, f, width - icon_size - 24)

        draw.rounded_rectangle((x, y, x + width, y + height), radius=5, fill=CHIP)
        draw.rounded_rectangle((x, y, x + width, y + height), radius=5, outline=BORDER, width=1)
        if icon is not None:
            canvas.alpha_composite(_round_image(icon, icon_size, radius=4), (x + 4, y + 4))
        if badge:
            self._icon_badge(draw, x + 4, y + 4, icon_size, badge, accent, align="left")
        draw.text((x + icon_size + 10, y + height / 2), label, font=f, fill=WHITE, anchor="lm")
        return x + width

    def _plot_chip(self, canvas, draw, x, y, width, icon, label, role_icon=None, height=36) -> int:
        f = _font(13, "medium")
        icon_size = height - 8
        label = _fit(draw, label, f, width - icon_size - 24)

        draw.rounded_rectangle((x, y, x + width, y + height), radius=5, fill=CHIP_PLOT)
        draw.rounded_rectangle((x, y, x + width, y + height), radius=5, outline=BORDER, width=1)
        if icon is not None:
            canvas.alpha_composite(_round_image(icon, icon_size, radius=4), (x + 4, y + 4))
            if role_icon is not None:
                canvas.alpha_composite(
                    _round_image(role_icon, 19, radius=10),
                    (x + 4 + icon_size - 13, y + 4 + icon_size - 13),
                )
        draw.text((x + icon_size + 11, y + height / 2), label, font=f, fill=(240, 239, 255, 255), anchor="lm")
        return x + width

    def _bonds(self, canvas, draw, lineup, icons, y) -> int:
        y = _section(draw, "Bond Information", y)
        traits = lineup.trait_list
        if not traits:
            draw.text((PAD + 2, y + 2), "No bonds recorded", font=_font(12, "medium"), fill=MUTED)
            return y + 30

        gap = 8
        col_w = (INNER - gap) // 2
        for i, trait in enumerate(traits):
            cx = PAD + (i % 2) * (col_w + gap)
            cy = y + (i // 2) * 38
            self._chip(
                canvas, draw, cx, cy, col_w,
                icons.get(trait.icon), trait.trait_name,
                badge=trait.trait_count,
                accent=_quality_color(trait.quality),
            )
        rows = (len(traits) + 1) // 2
        return y + rows * 38

    def _plot(self, canvas, draw, lineup, icons, y) -> int:
        y = _section(draw, "Plot Armor", y)
        spots = lineup.spot_light_list
        if not spots:
            draw.text((PAD + 2, y + 2), "No plot armor", font=_font(12, "medium"), fill=MUTED)
            return y + 28

        gap = 10
        width = min(250, (INNER - gap) // 2)
        for i, spot in enumerate(spots[:2]):
            cx = PAD + i * (width + gap)
            self._plot_chip(
                canvas, draw, cx, y, width,
                icons.get(spot.icon), spot.name,
                role_icon=icons.get(spot.role_icon or ""),
            )
        return y + 36

    def _invest(self, canvas, draw, lineup, icons, y) -> int:
        y = _section(draw, "Investment Environment", y)
        portal = lineup.portal_list[0] if lineup.portal_list else None
        if portal is not None:
            f = _font(13, "medium")
            width = int(draw.textlength(portal.name, font=f)) + 60
            self._chip(canvas, draw, PAD, y, width, icons.get(portal.icon), portal.name)
        else:
            draw.text((PAD + 2, y + 4), "No environment", font=_font(12, "medium"), fill=MUTED)
        y += 44

        y = _section(draw, "Investment Strategy", y)
        augments = lineup.augment_list
        if not augments:
            draw.text((PAD + 2, y + 2), "No strategy", font=_font(12, "medium"), fill=MUTED)
            return y + 30

        gap = 8
        col_w = (INNER - gap) // 2
        for i, aug in enumerate(augments):
            cx = PAD + (i % 2) * (col_w + gap)
            cy = y + (i // 2) * 38
            self._chip(
                canvas, draw, cx, cy, col_w,
                icons.get(aug.icon), aug.name,
                badge=aug.quality,
                accent=_quality_color(aug.quality),
            )
        rows = (len(augments) + 1) // 2
        return y + rows * 38

    # -- damage -----------------------------------------------------------

    def _damage(self, canvas, draw, lineup, icons, y) -> int:
        y = _section(draw, "DMG Statistics", y)
        traits = {t.trait_id: t for t in lineup.trait_list}
        roles = {r.role_id: r for r in list(lineup.front_roles) + list(lineup.back_roles)}

        rows: list[dict] = []
        for entry in lineup.damage_list:
            try:
                value = int(float(entry.damage))
            except (TypeError, ValueError):
                value = 0
            if entry.damage_type == "DamageTypeTrait" and entry.id in traits:
                trait = traits[entry.id]
                rows.append({
                    "value": value, "name": trait.trait_name, "icon": icons.get(trait.icon),
                    "role": None, "element": None,
                    "badge": trait.trait_count, "badge_color": _quality_color(trait.quality),
                })
            elif entry.id in roles:
                role = roles[entry.id]
                rows.append({
                    "value": value, "name": role.name, "icon": icons.get(role.icon),
                    "role": role, "element": self._element_color(role.avatar_id),
                    "badge": "", "badge_color": MUTED,
                })
            else:
                rows.append({
                    "value": value, "name": f"Unknown {entry.id}", "icon": None,
                    "role": None, "element": None,
                    "badge": "", "badge_color": MUTED,
                })
        rows.sort(key=lambda r: r["value"], reverse=True)
        if not rows:
            draw.text((PAD + 2, y + 2), "No damage recorded", font=_font(12, "medium"), fill=MUTED)
            return y + 30

        chart_h = 100
        chart_top = y + 26
        base = chart_top + chart_h
        draw.line((PAD, base, W - PAD, base), fill=(96, 91, 164, 255), width=1)

        col_w = INNER / len(rows)
        peak = max((r["value"] for r in rows), default=0) or 1
        avatar_size = 40 if col_w >= 60 else 34
        f_val = _font(12, "bold")
        f_name = _font(11, "bold")

        for i, row in enumerate(rows):
            cx = PAD + col_w * (i + 0.5)
            ratio = row["value"] / peak
            bar_h = max(3, int(chart_h * ratio))
            bar_w = 18 if col_w >= 60 else 13
            color = BAR if row["role"] is not None else BAR_TRAIT
            draw.rounded_rectangle((cx - bar_w / 2, base - bar_h, cx + bar_w / 2, base), radius=2, fill=color)

            label = "0" if row["value"] == 0 else _compact(row["value"])
            draw.text((cx, base - bar_h - 12), label, font=f_val, fill=CREAM, anchor="mm")

            icon = row["icon"]
            avatar_y = base + 8
            if icon is not None:
                if row["element"] is not None:
                    avatar = _ringed(icon, avatar_size - 4, row["element"] + (255,), width=2)
                else:
                    avatar = _round_image(icon, avatar_size, radius=avatar_size // 2)
                canvas.alpha_composite(avatar, (int(cx - avatar.width / 2), avatar_y))
            if row["badge"]:
                badge_w = avatar.width if icon is not None else avatar_size
                self._icon_badge(
                    draw,
                    int(cx + badge_w / 2 - 14), avatar_y + avatar_size - 16,
                    14, row["badge"], row["badge_color"],
                )

            role = row["role"]
            if role is not None:
                size = 14
                equips = role.equip_list[:3]
                total_w = len(equips) * size + max(0, len(equips) - 1) * 2
                for j, equip in enumerate(equips):
                    ex = int(cx - total_w / 2 + j * (size + 2))
                    ey = base + avatar_size + 14
                    draw.rounded_rectangle((ex, ey, ex + size, ey + size), radius=2, fill=(44, 41, 100, 255), outline=(86, 80, 166, 255), width=1)
                    e_icon = icons.get(equip.icon)
                    if e_icon is not None:
                        canvas.alpha_composite(_round_image(e_icon, size - 2, radius=2), (ex + 1, ey + 1))
            else:
                name = _fit(draw, row["name"], f_name, int(col_w) - 4)
                draw.text((cx, base + avatar_size + 24), name, font=f_name, fill=TEXT, anchor="mm")

        return base + avatar_size + 40
