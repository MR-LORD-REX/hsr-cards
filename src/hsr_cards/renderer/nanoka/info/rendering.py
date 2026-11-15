"""Compose synchronous character info, hero, materials, and comparison cards."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.info.drawing import base_canvas, identity, splash, version_pill
from hsr_cards.renderer.nanoka.info.materials import ascension_panel, compact_rows, comparison_rows, skills_panel
from hsr_cards.renderer.nanoka.info.models import CardData
from hsr_cards.renderer.nanoka.info.stats import draw_compact_stats_panel, draw_stats_panel
from hsr_cards.renderer.nanoka.info.styles import M
from hsr_cards.renderer.nanoka.info.text import heavy, ui


def footer(draw, width, height, data: CardData):
    """Draw build/comparison and locale provenance along the supplied canvas bottom."""
    draw.line((M, height - 44, width - M, height - 44), fill=LINE, width=1)
    if data.before is not None:
        label = f"NANOKA HSR  /  DATA v{data.before.version} \u2192 v{data.version}  /  {data.locale.upper()}"
    else:
        label = f"NANOKA HSR  /  DATA v{data.version}  /  {data.locale.upper()}"
    draw.text((M, height - 30), label, font=heavy(13, data.locale), fill=DIM)


def render_hero(data: CardData) -> Image.Image:
    """Draw resolved identity, stats and ascension costs as a 1080x1250 RGBA image.

    Accept CardData with prepared images/cache paths; read only cached art/fonts.
    No provider requests, schedule selection or generated-image writes occur.
    Font/image/layout errors propagate; this renderer owns no provider lifecycle.
    """
    width, height = 1080, 1250
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 640), fill=(12, 8, 23, 255))
    draw.line((M, 74, width - M, 74), fill=LINE, width=1)
    draw.text((M, 32), f"NANOKA / HSR  /  {ui(data, 'character_card')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 570, 576, 48)
    version_pill(canvas, draw, data, width, 26)
    identity(canvas, draw, data, M, 108, 78, 560, 2)
    draw_compact_stats_panel(canvas, draw, data, 650)
    ascension_panel(canvas, draw, data, 918, 232, 60, 21)
    footer(draw, width, height, data)
    return canvas


def render_materials(data: CardData) -> Image.Image:
    """Draw resolved ascension/skill material totals as a 1080x1250 RGBA image.

    Accept prepared CardData, including optional previous material quantities.
    Read cached art/fonts without requesting provider data or saving the image;
    font/image/layout errors propagate.
    """
    width, height = 1080, 1250
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 390), fill=(12, 8, 23, 255))
    draw.line((M, 72, width - M, 72), fill=LINE, width=1)
    draw.text((M, 30), f"NANOKA / HSR  /  {ui(data, 'materials')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 350, 674, 42)
    version_pill(canvas, draw, data, width, 24)
    identity(canvas, draw, data, M, 100, 62, 590, 2)
    ascension_panel(canvas, draw, data, 414, 250, 62, 21)
    skills_panel(canvas, draw, data, 738, 412, 56, 21)
    footer(draw, width, height, data)
    return canvas


def render_detail(data: CardData, with_voice: bool = False) -> Image.Image:
    """Draw complete character identity, level-80 stats and material totals.

    Return a 1080x1440 RGBA image for single-build data; attached previous data selects
    an inline comparison whose height may grow. with_voice remains a compatibility
    argument; voice labels are included by the stats panel. Read cached art/fonts
    only, with no provider requests or generated-image writes. Errors propagate.
    """
    if data.before is not None:
        return render_detail_comparison(data)
    width, height = 1080, 1440
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 430), fill=(12, 8, 23, 255))
    draw.line((M, 72, width - M, 72), fill=LINE, width=1)
    draw.text((M, 30), f"NANOKA / HSR  /  {ui(data, 'character_card')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 400, 650, 50)
    version_pill(canvas, draw, data, width, 24)
    identity(canvas, draw, data, M, 102, 66, 570, 3)
    draw_stats_panel(canvas, draw, data, 424, compact=False)
    ascension_panel(canvas, draw, data, 758, 220, 60, 21)
    skills_panel(canvas, draw, data, 1050, 286, 46, 19, row_h=42)
    footer(draw, width, height, data)
    return canvas


def render_detail_comparison(data: CardData) -> Image.Image:
    """Draw an inline info comparison with previous/current values and material changes.

    Require data.before. Return a 1080-pixel-wide RGBA image at least 1440 pixels tall,
    growing to fit measured material rows. Cached fonts/artwork may be read; no
    provider resources are opened and no generated image is saved.
    """
    asc_rows = compact_rows([row for row in comparison_rows(data.ascension, data.before.ascension) if row[0].item_id != 2], 4)
    skill_rows = compact_rows([row for row in comparison_rows(data.skills, data.before.skills) if row[0].item_id != 2], 8)
    asc_h = 220 + max(0, (len(asc_rows) + 1) // 2 - 2) * 72
    skill_row_h = 42
    skill_h = 286 + max(0, (len(skill_rows) + 1) // 2 - 4) * skill_row_h
    asc_y = 758
    skill_y = asc_y + 48 + asc_h + 24
    height = max(1440, skill_y + skill_h + 70)
    width = 1080
    canvas = base_canvas(width, height)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 430), fill=(12, 8, 23, 255))
    draw.line((M, 72, width - M, 72), fill=LINE, width=1)
    draw.text((M, 30), f"NANOKA / HSR  /  {ui(data, 'character_card')}", font=heavy(16 if data.locale != 'en' else 18, data.locale), fill=MUTED)
    splash(canvas, data, 400, 650, 50)
    version_pill(canvas, draw, data, width, 24)
    identity(canvas, draw, data, M, 102, 66, 570, 3)
    draw_stats_panel(canvas, draw, data, 424, compact=False)
    ascension_panel(canvas, draw, data, asc_y, asc_h, 60, 21)
    skills_panel(canvas, draw, data, skill_y, skill_h, 46, 19, row_h=skill_row_h)
    footer(draw, width, height, data)
    return canvas
