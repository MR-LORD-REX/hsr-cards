from __future__ import annotations
from io import BytesIO
from pathlib import Path
import asyncio
import math

import aiohttp
from PIL import Image, ImageDraw, ImageFilter

from ..models.events import Activity, RewardItem
from ..utils.hsrfonts import HSRFonts

_ASSETS   = Path(__file__).parent.parent / "assets"
_STAR_G   = _ASSETS / "backgrounds" / "ANO" / "star_gold.png"


BG        = (15,  15,  24,  255)
PANEL     = (24,  24,  36,  255)
CARD_BG   = (22,  22,  34,  255)
BORDER    = (45,  45,  65,  255)
GOLD      = (255, 200,  60,  255)
GOLD_DIM  = (180, 140,  40,  255)
PURPLE    = (170, 120, 255, 255)
GREEN     = ( 80, 210, 130,  255)
RED       = (240,  80,  80,  255)
WHITE     = (255, 255, 255,  255)
SUBTEXT   = (150, 155, 185,  255)
DIVIDER   = ( 42,  42,  62,  255)
BAR_BG    = ( 35,  35,  55,  255)
BAR_FILL  = ( 90, 200, 120,  255)
LOCKED_C  = (100, 100, 130,  255)

W          = 760
PAD        = 24
ROW_H      = 108
ICON_SZ    = 40
REWARD_SZ  = 36
CORNER     = 12

STATUS_COLORS = {
    "Completed": GREEN,
    "Locked":    LOCKED_C,
    "Incomplete": GOLD,
}


async def _fetch(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return Image.open(BytesIO(await r.read())).convert("RGBA")
    except Exception:
        pass
    return None


def _time_remaining(now_ts: str, end_ts: str) -> str:
    secs = int(end_ts) - int(now_ts)
    if secs <= 0:
        return "Ended"
    d, rem = divmod(secs, 86400)
    h, _   = divmod(rem, 3600)
    if d:
        return f"{d}d {h}h remaining"
    return f"{h}h remaining"


def _progress_bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
                  current: int, total: int):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=BAR_BG)
    if total > 0 and current > 0:
        fill_w = max(h, int(w * min(current, total) / total))
        draw.rounded_rectangle((x, y, x + fill_w, y + h), radius=h // 2, fill=BAR_FILL)


def _wrap_text(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _pill(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, font,
          bg=(40, 40, 65, 220), fg=WHITE) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    pw   = bbox[2] - bbox[0] + 14
    ph   = bbox[3] - bbox[1] + 6
    draw.rounded_rectangle((x, y, x + pw, y + ph), radius=ph // 2, fill=bg)
    draw.text((x + 7, y + 3), text, font=font, fill=fg)
    return pw


def _draw_reward_icon(card: Image.Image, icon: Image.Image | None,
                      rarity: str, num: int, x: int, y: int, sz: int):
    bg_col = (55, 38, 8, 255) if rarity == "5" else \
             (35, 25, 58, 255) if rarity == "4" else \
             (25, 35, 55, 255)
    border = (200, 140, 30, 255) if rarity == "5" else \
             (160, 110, 240, 255) if rarity == "4" else \
             (80, 110, 160, 255)

    slot = Image.new("RGBA", (sz, sz), bg_col)
    ImageDraw.Draw(slot).rounded_rectangle(
        (0, 0, sz - 1, sz - 1), radius=6, outline=border, width=1
    )
    if icon:
        ico = icon.resize((sz - 6, sz - 6), Image.LANCZOS)
        slot.alpha_composite(ico, (3, 3))
    if num > 1:
        d = ImageDraw.Draw(slot)
        f = HSRFonts.get_font(10, "bold")
        d.text((sz - 3, sz - 3), str(num), font=f, fill=WHITE, anchor="rb")
    card.alpha_composite(slot, (x, y))


async def _render_event_row(
    session: aiohttp.ClientSession,
    ev: Activity,
    y_offset: int,
    card_w: int,
    personalised: bool,
) -> tuple[Image.Image, int]:
    is_locked    = ev.show_text == "Locked"
    is_completed = ev.all_finished
    is_double    = ev.multiple_drop_type == 1 and ev.drop_multiple > 1

    usable_rewards = [r for r in ev.reward_list if r.num > 0 or ev.special_reward]
    if ev.special_reward and ev.special_reward not in usable_rewards:
        usable_rewards = [ev.special_reward] + [r for r in ev.reward_list if r.num > 0]

    n_reward_cols = min(len(usable_rewards), 10)
    reward_rows   = math.ceil(len(usable_rewards) / 10) if usable_rewards else 0

    row_h = 36                          
    row_h += 20                          
    if personalised and not is_locked:
        row_h += 22                      
    if usable_rewards:
        row_h += reward_rows * (REWARD_SZ + 6) + 24  
    row_h += PAD

    row = Image.new("RGBA", (card_w, row_h), CARD_BG)
    draw = ImageDraw.Draw(row)

    left_accent = GREEN if is_completed else GOLD if not is_locked else LOCKED_C
    draw.rectangle((0, 0, 3, row_h), fill=left_accent)
    draw.rounded_rectangle((0, 0, card_w - 1, row_h - 1),
                            radius=CORNER, outline=BORDER, width=1)

    f_name  = HSRFonts.get_font(16, "bold")
    f_small = HSRFonts.get_font(11, "medium")
    f_med   = HSRFonts.get_font(12, "bold")

    y = PAD // 2 + 6

    draw.text((PAD, y), ev.name, font=f_name, fill=WHITE if not is_locked else LOCKED_C)


    st_col = STATUS_COLORS.get(ev.show_text, SUBTEXT)
    _pill(draw, ev.show_text, card_w - PAD - 90, y + 2, f_small, bg=(*st_col[:3], 50), fg=st_col)
    if is_double:
        _pill(draw, f"x{ev.drop_multiple} Rewards", card_w - PAD - 180, y + 2,
              f_small, bg=(60, 30, 90, 180), fg=PURPLE)
    y += 24

    ti    = ev.time_info
    t_str = f"{ti.start_time[:16]}  –  {ti.end_time[:16]}"
    draw.text((PAD, y), t_str, font=f_small, fill=WHITE)
    remain = _time_remaining(ti.now, ti.end_ts)
    r_col  = RED if "1d" in remain or "Ended" in remain else GOLD
    draw.text((card_w - PAD, y), remain, font=f_small, fill=r_col, anchor="ra")
    y += 18

    if personalised and not is_locked and ev.total_progress > 0:
        bar_w = card_w - PAD * 2
        _progress_bar(draw, PAD, y, bar_w, 8, ev.current_progress, ev.total_progress)
        prog_text = f"{ev.current_progress} / {ev.total_progress}"
        draw.text((PAD + bar_w + 4, y - 2), prog_text, font=f_small, fill=WHITE)
        y += 22

    if usable_rewards:
        y += 6
        draw.text((PAD, y), "Rewards", font=f_med, fill=GOLD)
        y += 18

        icon_tasks = [_fetch(session, r.icon) for r in usable_rewards]
        icons = list(await asyncio.gather(*icon_tasks))

        for idx, (reward, icon) in enumerate(zip(usable_rewards, icons)):
            col = idx % 10
            r   = idx // 10
            rx  = PAD + col * (REWARD_SZ + 6)
            ry  = y + r * (REWARD_SZ + 6)
            _draw_reward_icon(row, icon, reward.rarity, reward.num, rx, ry, REWARD_SZ)

    return row, row_h


async def render_events_card(
    activities: list[Activity],
    personalised: bool,
    now_ts: str,
) -> Image.Image:
    session = aiohttp.ClientSession()
    try:
        acts = [a for a in activities
                if a.act_type in ("ActivityTypeOther", "ActivityTypeSign", "ActivityTypeDouble")]

        INNER_W = W - PAD * 2

        row_tasks = [
            _render_event_row(session, ev, 0, INNER_W, personalised)
            for ev in acts
        ]
        rows = list(await asyncio.gather(*row_tasks))

        total_h = PAD + 56 + sum(h for _, h in rows) + (len(rows) - 1) * 8 + PAD

        canvas = Image.new("RGBA", (W, total_h), BG)
        draw   = ImageDraw.Draw(canvas)

        bar = Image.new("RGBA", (W, 4), (0, 0, 0, 0))
        for x in range(W):
            t = x / W
            r = int(GOLD[0] * (1 - t) + PURPLE[0] * t)
            g = int(GOLD[1] * (1 - t) + PURPLE[1] * t)
            b = int(GOLD[2] * (1 - t) + PURPLE[2] * t)
            bar.putpixel((x, 0), (r, g, b, 255))
            bar.putpixel((x, 1), (r, g, b, 160))
            bar.putpixel((x, 2), (r, g, b, 60))
        canvas.alpha_composite(bar, (0, 0))

        f_title = HSRFonts.get_font(26, "bold")
        f_sub   = HSRFonts.get_font(12, "light")
        draw.text((PAD, PAD + 4), "Events", font=f_title, fill=WHITE)
        mode_txt = "Personalised  •  Progress Tracking" if personalised else "Public  •  Rewards Overview"
        draw.text((PAD, PAD + 36), mode_txt, font=f_sub, fill=SUBTEXT)
        draw.line((PAD, PAD + 54, W - PAD, PAD + 54), fill=DIVIDER, width=1)

        y = PAD + 62
        for row_img, row_h in rows:
            canvas.alpha_composite(row_img, (PAD, y))
            y += row_h + 8

        return canvas.convert("RGB")
    finally:
        await session.close()


class EventsRenderer:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def render_events(
        self,
        activities: list[Activity],
        personalised: bool,
        now_ts: str,
    ) -> Image.Image:
        return await render_events_card(activities, personalised, now_ts)
