"""Compatibility exports for the extracted character renderer and service."""
from hsr_cards.renderer.nanoka.info.styles import (
    ADDED_COLOR,
    ARROW_COLOR,
    BASIC_STAT_ICONS,
    BONUS_ICONS,
    CARD_EDGE,
    CARD_FILL,
    CONTENT_W,
    DETAIL_PUNCT,
    ELEMENT_LABELS,
    M,
    PATH_LABELS,
    REMOVED_COLOR,
    SOFT_EDGE,
    UI_LABELS,
)
from hsr_cards.renderer.nanoka.info.text import (
    _detail_units,
    draw_detail_lines,
    fit,
    heavy,
    layout_detail_lines,
    text_locale,
    ui,
    wrap_text,
)
from hsr_cards.renderer.nanoka.info.models import (
    CardData,
    DetailPiece,
)
from hsr_cards.renderer.nanoka.info.drawing import (
    _strike,
    base_canvas,
    change_overlay,
    heading,
    identity,
    splash,
    tag,
    variation_text,
    version_pill,
)
from hsr_cards.renderer.nanoka.info.materials import (
    _amount,
    _credits_value,
    ascension_panel,
    compact_rows,
    compare_costs,
    comparison_rows,
    credits_strip,
    material_item,
    skills_panel,
)
from hsr_cards.renderer.nanoka.info.stats import (
    bonus_icon_name,
    draw_compact_stats_panel,
    draw_stats_panel,
    stat_icon,
    stat_row,
    stat_row_removed,
)
from hsr_cards.renderer.nanoka.info.rendering import (
    footer,
    render_detail,
    render_detail_comparison,
    render_hero,
    render_materials,
)
from hsr_cards.services.character_info import (
    build_card_data,
    build_comparison_card_data,
    load_data,
)
from hsr_cards.renderer.nanoka.info.cli import (
    build_all,
    main,
)
from hsr_cards.renderer.nanoka.character_info import BG
from hsr_cards.renderer.nanoka.character_info import BONUS_LABELS
from hsr_cards.renderer.nanoka.data import CharacterData
from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import FIRE
from hsr_cards.renderer.nanoka.character_info import GOLD
from PIL import Image
from PIL import ImageDraw
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import PURPLE
from pathlib import Path
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import aggregate
import argparse
from hsr_cards.renderer.nanoka.character_info import asset
import asyncio
from hsr_cards.renderer.nanoka.character_info import bonus_stats
from hsr_cards.renderer.nanoka.character_info import clean_localized
from hsr_cards.renderer.nanoka.character_info import composite_panel
from dataclasses import dataclass
from hsr_cards.renderer.nanoka.diff import diff_words
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import format_bonus
from hsr_cards.renderer.nanoka.data import load_character
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.character_info import make_star
from hsr_cards.renderer.nanoka.character_info import material_name
from hsr_cards.renderer.nanoka.character_info import max_stats
from hsr_cards.renderer.nanoka.data import prime_assets
from hsr_cards.renderer.nanoka.character_info import radial
import re
from hsr_cards.renderer.nanoka.character_info import skill_materials
import sys
from hsr_cards.renderer.nanoka.character_info import wrap

if __name__ == '__main__':
    main()
