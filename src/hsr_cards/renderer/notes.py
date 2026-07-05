from __future__ import annotations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ..models.notes import NotesData
from ..utils.hsrfonts import HSRFonts

_ASSETS   = Path(__file__).parent.parent / "assets"
_RESIN    = _ASSETS / "general" / "resin.png"

BG        = (14,  14,  22,  255)
PANEL     = (22,  22,  34,  255)
CARD_BG   = (20,  20,  32,  255)
BORDER    = (44,  44,  64,  255)
GOLD      = (255, 200,  55,  255)
PURPLE    = (170, 120, 255, 255)
GREEN     = ( 80, 215, 135,  255)
CYAN      = ( 80, 200, 230,  255)
RED       = (240,  80,  80,  255)
WHITE     = (255, 255, 255,  255)
SUBTEXT   = (160, 165, 200,  255)
DIVIDER   = ( 40,  40,  60,  255)
BAR_BG    = ( 30,  30,  50,  255)

W, PAD = 720, 24
CORNER  = 14


def _bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
         cur: int, mx: int, fill_col, bg=BAR_BG):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg)
    if mx > 0 and cur > 0:
        fw = max(h, int(w * min(cur, mx) / mx))
        draw.rounded_rectangle((x, y, x + fw, y + h), radius=h // 2, fill=fill_col)


def _stamina_color(cur: int, mx: int) -> tuple:
    ratio = cur / mx if mx else 0
    if ratio >= 1.0:
        return GREEN
    if ratio >= 0.5:
        return CYAN
    return PURPLE


def _seconds_to_str(secs: int) -> str:
    if secs <= 0:
        return "Full"
    d, r  = divmod(secs, 86400)
    h, r2 = divmod(r, 3600)
    m     = r2 // 60
    if d:
        return f"{d}d {h:02d}h {m:02d}m"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def _stat_cell(canvas: Image.Image, draw: ImageDraw.ImageDraw,
               label: str, value: str, sub: str,
               x: int, y: int, w: int, h: int,
               val_col=WHITE):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=PANEL, outline=BORDER, width=1)
    f_lbl = HSRFonts.get_font(11, "medium")
    f_val = HSRFonts.get_font(22, "bold")
    f_sub = HSRFonts.get_font(11, "medium")
    draw.text((x + 14, y + 10), label, font=f_lbl, fill=SUBTEXT)
    draw.text((x + 14, y + 26), value, font=f_val, fill=val_col)
    if sub:
        draw.text((x + 14, y + 56), sub, font=f_sub, fill=SUBTEXT)


def render_notes_card(data: NotesData) -> Image.Image:
    resin_img = Image.open(_RESIN).convert("RGBA").resize((48, 48), Image.LANCZOS)

    stamina_col = _stamina_color(data.current_stamina, data.max_stamina)
    recover_str = _seconds_to_str(data.stamina_recover_time)

    TOTAL_H = PAD + 56 + 20 + PAD + 100 + 16 + 80 + PAD
    canvas  = Image.new("RGBA", (W, TOTAL_H), BG)
    draw    = ImageDraw.Draw(canvas)

    bar = Image.new("RGBA", (W, 4), (0, 0, 0, 0))
    for x in range(W):
        t = x / W
        r = int(GOLD[0] * (1 - t) + PURPLE[0] * t)
        g = int(GOLD[1] * (1 - t) + PURPLE[1] * t)
        b = int(GOLD[2] * (1 - t) + PURPLE[2] * t)
        bar.putpixel((x, 0), (r, g, b, 255))
        bar.putpixel((x, 1), (r, g, b, 140))
        bar.putpixel((x, 2), (r, g, b, 50))
    canvas.alpha_composite(bar, (0, 0))

    # ── header ────────────────────────────────────────────────────────────────
    y = PAD + 4
    f_title = HSRFonts.get_font(24, "bold")
    f_sub   = HSRFonts.get_font(12, "medium")
    draw.text((PAD + 4, y), "✦", font=HSRFonts.get_font(18, "bold"), fill=GOLD)
    draw.text((PAD + 24, y + 2), "Real-Time Notes", font=f_title, fill=WHITE)
    draw.text((PAD + 4, y + 34), "Personalised  •  Live data", font=f_sub, fill=SUBTEXT)
    draw.line((PAD, y + 52, W - PAD, y + 52), fill=DIVIDER, width=1)
    y += 60

    # ═══════════════════════════════════════════════════════════════════════
    # STAMINA ROW
    # ═══════════════════════════════════════════════════════════════════════
    STAMP_PANEL_H = 96
    draw.rounded_rectangle(
        (PAD, y, W - PAD, y + STAMP_PANEL_H),
        radius=CORNER, fill=PANEL, outline=BORDER, width=1
    )

    # Trailblaze Power (left half)
    canvas.alpha_composite(resin_img, (PAD + 16, y + (STAMP_PANEL_H - 48) // 2))

    f_big  = HSRFonts.get_font(28, "bold")
    f_med  = HSRFonts.get_font(12, "medium")
    f_sm   = HSRFonts.get_font(11, "medium")

    lx = PAD + 16 + 48 + 12
    draw.text((lx, y + 14), f"{data.current_stamina}", font=f_big, fill=stamina_col)
    draw.text((lx + draw.textlength(str(data.current_stamina), font=f_big) + 4,
               y + 22), f"/ {data.max_stamina}", font=f_med, fill=SUBTEXT)
    sub_line = "Full" if data.stamina_recover_time <= 0 else f"Full in {recover_str}"
    draw.text((lx, y + 50), sub_line, font=f_sm, fill=SUBTEXT)

    # stamina bar
    bar_x, bar_y = lx, y + 68
    bar_w = (W - PAD * 2) // 2 - 90
    _bar(draw, bar_x, bar_y, bar_w, 8, data.current_stamina, data.max_stamina, stamina_col)

    # Divider
    mid = W // 2
    draw.line((mid, y + 16, mid, y + STAMP_PANEL_H - 16), fill=DIVIDER, width=1)

    # Reserve stamina (right half)
    rx = mid + 16
    draw.text((rx, y + 14), str(data.current_reserve_stamina), font=f_big, fill=CYAN)
    draw.text((rx, y + 50), "Reserved Trailblaze Power", font=f_sm, fill=SUBTEXT)
    reserve_ratio = min(data.current_reserve_stamina / 2400, 1.0)
    r_bar_w = (W - PAD * 2) // 2 - 30
    _bar(draw, rx, y + 68, r_bar_w, 8, data.current_reserve_stamina, 2400, CYAN)

    y += STAMP_PANEL_H + 16

    # ═══════════════════════════════════════════════════════════════════════
    # STATS GRID  (5 cells)
    # ═══════════════════════════════════════════════════════════════════════
    CELL_H = 80
    inner  = W - PAD * 2
    GAP    = 10
    COLS   = 5
    cw     = (inner - GAP * (COLS - 1)) // COLS

    cells = [
        ("Daily Training",      f"{data.current_train_score}/{data.max_train_score}",
         "Points today",
         GREEN if data.current_train_score >= data.max_train_score else WHITE),
        ("Echo of War",         f"{data.weekly_cocoon_cnt}/{data.weekly_cocoon_limit}",
         "Weekly uses",
         GREEN if data.weekly_cocoon_cnt >= data.weekly_cocoon_limit else WHITE),
        ("Simulated Universe",  f"{data.current_rogue_score}/{data.max_rogue_score}",
         "Weekly score",
         GREEN if data.current_rogue_score >= data.max_rogue_score else GOLD),
        ("Divergent Universe",  f"{data.rogue_tourn_weekly_cur}/{data.rogue_tourn_weekly_max}",
         "Weekly points",
         GREEN if data.rogue_tourn_weekly_cur >= data.rogue_tourn_weekly_max else GOLD),
        ("Expeditions",
         f"{data.accepted_epedition_num}/{data.total_expedition_num}",
         "Active dispatches",
         GREEN if data.accepted_epedition_num == data.total_expedition_num else PURPLE),
    ]

    for i, (label, val, sub, col) in enumerate(cells):
        cx = PAD + i * (cw + GAP)
        _stat_cell(canvas, draw, label, val, sub, cx, y, cw, CELL_H, val_col=col)

    return canvas.convert("RGB")


class NotesRenderer:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def render_notes(self, data: NotesData) -> Image.Image:
        return render_notes_card(data)
