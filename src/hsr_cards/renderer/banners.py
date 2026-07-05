from __future__ import annotations
from io import BytesIO
from pathlib import Path
import math
import aiohttp
import asyncio
from PIL import Image, ImageDraw, ImageFilter

from ..models.events import CalendarData, CardPool, PoolAvatar, PoolEquip
from ..utils.hsrfonts import HSRFonts
from ..utils.elements import Elements

_ASSETS   = Path(__file__).parent.parent / "assets"
_STAR_GOLD = _ASSETS / "backgrounds" / "ANO" / "star_gold.png"
_STAR_NORM = _ASSETS / "backgrounds" / "ANO" / "star_normal.png"

# ── Palette ────────────────────────────────────────────────────────────────────
BG         = (14,  14,  22,  255)
PANEL      = (24,  24,  38,  255)
PANEL_ALT  = (20,  20,  32,  255)
CARD_5     = (52,  34,   8,  255)
CARD_4     = (32,  22,  55,  255)
GOLD       = (255, 200,  60,  255)
PURPLE     = (180, 130, 255,  255)
BLUE       = (100, 180, 255,  255)
WHITE      = (255, 255, 255,  255)
SUBTEXT    = (150, 150, 185,  255)
DIVIDER    = (45,  45,  70,  255)
GREEN      = (80,  200, 120,  255)  
AMBER      = (255, 170,  40,  255)  
COLLAB_COL = (220, 160, 255,  255)  
NEW_BADGE  = (255,  60,  80,  255)  

CARD_W, CARD_H = 72, 72
CARD_GAP       = 8
PAD            = 22
POOL_GAP       = 14
POOL_INNER     = 16      



async def _fetch_image(session: aiohttp.ClientSession, url: str,
                       size: tuple[int, int] = (CARD_W, CARD_H)) -> Image.Image:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                img = Image.open(BytesIO(await r.read())).convert("RGBA")
                return img.resize(size, Image.LANCZOS)
    except Exception:
        pass
    return Image.new("RGBA", size, (50, 50, 70, 255))


def _tint(img: Image.Image, color: tuple) -> Image.Image:
    r, g, b, _ = color
    overlay = Image.new("RGBA", img.size, (r, g, b, 255))
    overlay.putalpha(img.split()[3])
    return overlay


def _star_row(count: int, rarity: str) -> Image.Image:
    gold = Image.open(_STAR_GOLD).convert("RGBA").resize((14, 14))
    color = GOLD if rarity == "5" else PURPLE if rarity == "4" else BLUE
    row = Image.new("RGBA", (count * 15, 14), (0, 0, 0, 0))
    for i in range(count):
        s = _tint(gold.copy(), color)
        row.paste(s, (i * 15, 0), s)
    return row


def _time_status(pool: CardPool) -> tuple[str, tuple]:
    """Returns (label_text, label_colour) based on timing."""
    ti = pool.time_info
    try:
        now_ts   = int(ti.now)
        start_ts = int(ti.start_ts)
        end_ts   = int(ti.end_ts)
    except (ValueError, AttributeError):
        return ("Upcoming", AMBER)

    if pool.gacha_time_type == "GachaTimeTypeLong":
        start_str = ti.start_time[:10] if ti.start_time else "?"
        if now_ts < start_ts:
            diff = start_ts - now_ts
            d, h = diff // 86400, (diff % 86400) // 3600
            return (f"Unlocks in {d}d {h}h  ({start_str})", COLLAB_COL)
        return (f"Permanent / Collab  (from {start_str})", COLLAB_COL)

    if pool.is_after_version or now_ts < start_ts:
        diff = start_ts - now_ts
        d, h = diff // 86400, (diff % 86400) // 3600
        start_str = ti.start_time[:10] if ti.start_time else "?"
        return (f"Unlocks in {d}d {h}h  ({start_str})", AMBER)

    if end_ts > 0:
        diff = end_ts - now_ts
        if diff > 0:
            d, h = diff // 86400, (diff % 86400) // 3600
            end_str = ti.end_time[:10] if ti.end_time else "?"
            return (f"Active · {d}d {h}h left  (ends {end_str})", GREEN)
        return ("Ended", SUBTEXT)

    return ("Active", GREEN)


def _gradient_bar(width: int, height: int, c1: tuple, c2: tuple) -> Image.Image:
    bar = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for x in range(width):
        t = x / max(width - 1, 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        for y in range(height):
            a = int(255 * (1 - y / height))
            bar.putpixel((x, y), (r, g, b, a))
    return bar


def _pill(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
          font, bg: tuple, fg: tuple = WHITE) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    pw = bbox[2] - bbox[0] + 12
    ph = bbox[3] - bbox[1] + 6
    draw.rounded_rectangle((x, y, x + pw, y + ph), radius=ph // 2, fill=bg)
    draw.text((x + 6, y + 3), text, font=font, fill=fg)
    return pw




async def _avatar_card(session: aiohttp.ClientSession, av: PoolAvatar) -> Image.Image:
    card = Image.new("RGBA", (CARD_W, CARD_H), CARD_5 if av.rarity == "5" else CARD_4)
    art  = await _fetch_image(session, av.item_avatar_icon_path)
    card.alpha_composite(art)


    try:
        if av.damage_type_name:
            el = Elements.get_element(av.damage_type_name).convert("RGBA").resize((18, 18))
            bg_c = Image.new("RGBA", (22, 22), (0, 0, 0, 0))
            ImageDraw.Draw(bg_c).ellipse((0, 0, 21, 21), fill=(0, 0, 0, 150))
            card.alpha_composite(bg_c, (3, 3))
            card.alpha_composite(el, (5, 5))
    except Exception:
        pass

    
    if av.is_forward:
        draw = ImageDraw.Draw(card)
        f = HSRFonts.get_font(9, "bold")
        _pill(draw, "NEW", CARD_W - 30, 3, f, NEW_BADGE)

    border = GOLD if av.rarity == "5" else PURPLE
    ImageDraw.Draw(card).rounded_rectangle(
        (0, 0, CARD_W - 1, CARD_H - 1), radius=8, outline=border, width=2)

    return card


async def _equip_card(session: aiohttp.ClientSession, eq: PoolEquip) -> Image.Image:
    card = Image.new("RGBA", (CARD_W, CARD_H), CARD_5 if eq.rarity == "5" else CARD_4)
    art  = await _fetch_image(session, eq.item_url)
    card.alpha_composite(art)

    if eq.is_forward:
        draw = ImageDraw.Draw(card)
        f = HSRFonts.get_font(9, "bold")
        _pill(draw, "NEW", CARD_W - 30, 3, f, NEW_BADGE)

    border = GOLD if eq.rarity == "5" else PURPLE
    ImageDraw.Draw(card).rounded_rectangle(
        (0, 0, CARD_W - 1, CARD_H - 1), radius=8, outline=border, width=2)

    return card


def _pool_row_height(item_count: int) -> int:
    """Single-row of cards (no wrapping), plus header area."""
    return POOL_INNER * 2 + 32 + 8 + CARD_H + 4   # header + gap + cards + stars


async def _render_pool_row(
    session: aiohttp.ClientSession,
    pool: CardPool,
    width: int,
    is_char: bool,
) -> Image.Image:
    items = pool.avatar_list if is_char else pool.equip_list
    count = len(items)

    row_h = _pool_row_height(count)
    row   = Image.new("RGBA", (width, row_h), PANEL)
    draw  = ImageDraw.Draw(row)

    # subtle left accent line
    accent = GOLD if is_char else PURPLE
    draw.rectangle((0, 0, 3, row_h), fill=accent)

    # version pill
    f_ver  = HSRFonts.get_font(11, "bold")
    f_stat = HSRFonts.get_font(11, "medium")
    f_name = HSRFonts.get_font(13, "bold")

    x_cur = POOL_INNER + 6
    ver_w = _pill(draw, f"v{pool.version}", x_cur, POOL_INNER, f_ver,
                  (60, 40, 10, 220) if is_char else (38, 22, 65, 220),
                  GOLD if is_char else PURPLE)
    x_cur += ver_w + 8

    # time/status pill
    status_text, status_col = _time_status(pool)
    r, g, b, _ = status_col
    _pill(draw, status_text, x_cur, POOL_INNER, f_stat, (r, g, b, 40), status_col)

    # cards
    card_y = POOL_INNER + 32 + 8
    tasks = ([_avatar_card(session, a) for a in pool.avatar_list] if is_char
             else [_equip_card(session, e) for e in pool.equip_list])
    cards = list(await asyncio.gather(*tasks))

    for i, cimg in enumerate(cards):
        cx = POOL_INNER + 6 + i * (CARD_W + CARD_GAP)
        row.alpha_composite(cimg, (cx, card_y))

    # divider line at bottom
    draw.line((0, row_h - 1, width, row_h - 1), fill=DIVIDER, width=1)
    return row



async def render_banner_card(cal: CalendarData) -> Image.Image:
    session = aiohttp.ClientSession()
    try:
        char_pools  = cal.avatar_card_pool_list
        equip_pools = cal.equip_card_pool_list

        TITLE_H  = 64
        SEP_H    = 36
        INTER    = 6
        COL_GAP  = 14

        # Each column is sized to its own widest pool row
        max_char_items  = max((len(p.avatar_list) for p in char_pools),  default=1)
        max_equip_items = max((len(p.equip_list)  for p in equip_pools), default=1)

        col_char_w  = POOL_INNER * 2 + 6 + max_char_items  * (CARD_W + CARD_GAP) - CARD_GAP
        col_equip_w = POOL_INNER * 2 + 6 + max_equip_items * (CARD_W + CARD_GAP) - CARD_GAP

        W = PAD + col_char_w + COL_GAP + 1 + COL_GAP + col_equip_w + PAD

        char_rows_h  = SEP_H + sum(_pool_row_height(len(p.avatar_list)) + INTER for p in char_pools)
        equip_rows_h = SEP_H + sum(_pool_row_height(len(p.equip_list))  + INTER for p in equip_pools)
        col_h   = max(char_rows_h, equip_rows_h)
        total_h = PAD + TITLE_H + col_h + PAD

        canvas = Image.new("RGBA", (W, total_h), BG)
        draw   = ImageDraw.Draw(canvas)

        # Gradient bar at top
        bar = _gradient_bar(W, 4, GOLD, PURPLE)
        canvas.alpha_composite(bar, (0, 0))

        # Title
        y = PAD
        draw.text((PAD, y),      "Event Warps",                          font=HSRFonts.get_font(26, "bold"),  fill=WHITE)
        draw.text((PAD, y + 30), f"Game version  v{cal.cur_game_version}", font=HSRFonts.get_font(12, "light"), fill=SUBTEXT)
        y += TITLE_H
        draw.line((PAD, y - 6, W - PAD, y - 6), fill=DIVIDER, width=1)

        # Column x positions
        left_x  = PAD
        div_x   = PAD + col_char_w + COL_GAP
        right_x = div_x + 1 + COL_GAP
        draw.line((div_x, y, div_x, total_h - PAD), fill=DIVIDER, width=1)

        # Render all pool rows concurrently
        char_tasks  = [_render_pool_row(session, p, col_char_w,  is_char=True)  for p in char_pools]
        equip_tasks = [_render_pool_row(session, p, col_equip_w, is_char=False) for p in equip_pools]
        char_images, equip_images = await asyncio.gather(
            asyncio.gather(*char_tasks),
            asyncio.gather(*equip_tasks),
        )

        f_sec = HSRFonts.get_font(14, "bold")

        # Left column
        cy = y
        draw.rounded_rectangle((left_x, cy, left_x + col_char_w, cy + 28), radius=6, fill=(60, 40, 10, 60))
        draw.text((left_x + 10, cy + 6), "Character Event Warp", font=f_sec, fill=GOLD)
        cy += SEP_H
        for row_img in char_images:
            canvas.alpha_composite(row_img, (left_x, cy))
            cy += row_img.height + INTER

        # Right column
        ey = y
        draw.rounded_rectangle((right_x, ey, right_x + col_equip_w, ey + 28), radius=6, fill=(38, 22, 65, 60))
        draw.text((right_x + 10, ey + 6), "Light Cone Event Warp", font=f_sec, fill=PURPLE)
        ey += SEP_H
        for row_img in equip_images:
            canvas.alpha_composite(row_img, (right_x, ey))
            ey += row_img.height + INTER

        return canvas.convert("RGB")

    finally:
        await session.close()


class BannerRenderer:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def render_banners(self, cal: CalendarData) -> Image.Image:
        return await render_banner_card(cal)
