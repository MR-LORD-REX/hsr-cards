from __future__ import annotations
from io import BytesIO
from pathlib import Path
import asyncio
import math

import aiohttp
from PIL import Image, ImageDraw

from ..models.events import Challenge, RewardItem
from ..utils.hsrfonts import HSRFonts

_ASSETS   = Path(__file__).parent.parent / "assets"

# palette
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
BLUE      = (100, 180, 255, 255)

W          = 760
PAD        = 24
REWARD_SZ  = 36
CORNER     = 12

STATUS_COLORS = {
    "Completed": GREEN,
    "Locked":    LOCKED_C,
    "challengeStatusUnopened": LOCKED_C,
    "challengeStatusFinish": GREEN,
    "challengeStatusInProgress": GOLD,
}

async def _fetch(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    try:
        if not url: return None
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

async def _render_challenge_row(
    session: aiohttp.ClientSession,
    ch: Challenge,
    y_offset: int,
    card_w: int,
    personalised: bool,
) -> tuple[Image.Image, int]:
    is_locked = ch.status == "challengeStatusUnopened" or ch.show_text == "Locked"
    is_completed = ch.status == "challengeStatusFinish" or ch.show_text == "Completed" or ch.show_text == f"{ch.total_progress}/{ch.total_progress}"

    usable_rewards = [r for r in ch.reward_list if r.num > 0]
    if ch.special_reward and ch.special_reward not in usable_rewards:
        usable_rewards = [ch.special_reward] + usable_rewards

    reward_rows = math.ceil(len(usable_rewards) / 10) if usable_rewards else 0

    row_h = 36                          
    row_h += 20                          
    if usable_rewards:
        row_h += reward_rows * (REWARD_SZ + 6) + 24  
    row_h += PAD

    row = Image.new("RGBA", (card_w, row_h), CARD_BG)
    draw = ImageDraw.Draw(row)

    left_accent = BLUE if is_completed else GOLD if not is_locked else LOCKED_C
    draw.rectangle((0, 0, 3, row_h), fill=left_accent)
    draw.rounded_rectangle((0, 0, card_w - 1, row_h - 1),
                            radius=CORNER, outline=BORDER, width=1)

    f_name  = HSRFonts.get_font(16, "bold")
    f_small = HSRFonts.get_font(11, "medium")
    f_med   = HSRFonts.get_font(12, "bold")

    y = PAD // 2 + 6
    

    icon_w = 0
    icon_img = None
    if ch.challenge_peak_rank_icon:
        icon_img = await _fetch(session, ch.challenge_peak_rank_icon)
    
    if icon_img:
        icon_img = icon_img.resize((24, 24), Image.LANCZOS)
        row.alpha_composite(icon_img, (PAD, y - 2))
        icon_w = 30

    type_map = {
        "ChallengeTypeStory": "Pure Fiction",
        "ChallengeTypePeak": "Anomaly Arbitration",
        "ChallengeTypeChasm": "Forgotten Hall",
        "ChallengeTypeBoss": "Apocalyptic Shadow"
    }
    prefix = type_map.get(ch.challenge_type, "")
    display_name = f"{prefix} - {ch.name_mi18n}" if prefix else ch.name_mi18n

    draw.text((PAD + icon_w, y), display_name, font=f_name, fill=WHITE if not is_locked else LOCKED_C)

    if personalised:
        st_col = STATUS_COLORS.get(ch.show_text, STATUS_COLORS.get(ch.status, SUBTEXT))
        if st_col == SUBTEXT and ("/" in ch.show_text or "★" in ch.show_text):
            st_col = GOLD if not is_completed else GREEN
        
        status_text = ch.show_text if ch.show_text else ("Completed" if is_completed else ("Locked" if is_locked else "In Progress"))
        
        if ch.extra_progress > 0 and ch.show_text == "Incomplete":
            # Just fallback to generic text if it's incomplete
            pass
            
        _pill(draw, status_text, card_w - PAD - max(120, draw.textlength(status_text, font=f_small) + 30), y + 2, f_small, bg=(*st_col[:3], 50), fg=st_col)
    
    y += 24

    ti    = ch.time_info
    t_str = f"{ti.start_time[:16]}  –  {ti.end_time[:16]}"
    draw.text((PAD, y), t_str, font=f_small, fill=WHITE)
    
    if ti.end_ts and ti.end_ts != "0":
        remain = _time_remaining(ti.now, ti.end_ts)
        r_col  = RED if "1d" in remain or "Ended" in remain or "0d" in remain else GOLD
        draw.text((card_w - PAD, y), remain, font=f_small, fill=r_col, anchor="ra")
    y += 18

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

async def render_endgame_card(
    challenges: list[Challenge],
    personalised: bool,
    now_ts: str,
) -> Image.Image:
    session = aiohttp.ClientSession()
    try:
        INNER_W = W - PAD * 2

        row_tasks = [
            _render_challenge_row(session, ch, 0, INNER_W, personalised)
            for ch in challenges
        ]
        rows = list(await asyncio.gather(*row_tasks))
        
        if not rows:
            rows = [(Image.new("RGBA", (INNER_W, 60), CARD_BG), 60)]
            d = ImageDraw.Draw(rows[0][0])
            d.text((PAD, 20), "No active endgame modes available.", font=HSRFonts.get_font(14, "medium"), fill=SUBTEXT)

        total_h = PAD + 56 + sum(h for _, h in rows) + max(0, len(rows) - 1) * 8 + PAD

        canvas = Image.new("RGBA", (W, total_h), BG)
        draw   = ImageDraw.Draw(canvas)

        bar = Image.new("RGBA", (W, 4), (0, 0, 0, 0))
        for x in range(W):
            t = x / W
            r = int(BLUE[0] * (1 - t) + PURPLE[0] * t)
            g = int(BLUE[1] * (1 - t) + PURPLE[1] * t)
            b = int(BLUE[2] * (1 - t) + PURPLE[2] * t)
            bar.putpixel((x, 0), (r, g, b, 255))
            bar.putpixel((x, 1), (r, g, b, 160))
            bar.putpixel((x, 2), (r, g, b, 60))
        canvas.alpha_composite(bar, (0, 0))

        f_title = HSRFonts.get_font(26, "bold")
        f_sub   = HSRFonts.get_font(12, "light")
        draw.text((PAD, PAD + 4), "Endgame Modes", font=f_title, fill=WHITE)
        mode_txt = "Personalised  •  Progress Tracking" if personalised else "Public  •  Schedule Overview"
        draw.text((PAD, PAD + 36), mode_txt, font=f_sub, fill=SUBTEXT)
        draw.line((PAD, PAD + 54, W - PAD, PAD + 54), fill=DIVIDER, width=1)

        y = PAD + 62
        for row_img, row_h in rows:
            canvas.alpha_composite(row_img, (PAD, y))
            y += row_h + 8

        return canvas.convert("RGB")
    finally:
        await session.close()

class EndgameRenderer:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def render_endgame(
        self,
        challenges: list[Challenge],
        personalised: bool,
        now_ts: str,
    ) -> Image.Image:
        return await render_endgame_card(challenges, personalised, now_ts)
