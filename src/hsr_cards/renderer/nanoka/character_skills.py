"""Compatibility exports for the extracted character renderer and service."""
from hsr_cards.renderer.nanoka.skills.styles import (
    BODY,
    BODY_SOFT,
    BOTTOM_RESERVE,
    CARD_EDGE,
    CARD_FILL,
    CHANGED_VALUE_KINDS,
    CONTENT_TOP,
    DASH,
    DECIMAL,
    DESC_SPLIT_H,
    DESC_TARGET_H,
    EIDOLON_VALUE,
    EID_BOTTOM,
    EID_GAP,
    EID_PAD,
    EID_TITLE_SIZE,
    EID_TITLE_STEP,
    EID_W,
    ELEMENT_LABELS,
    FALLBACK_CHARS,
    FONT_DIR,
    FONT_SEMI_FILE,
    FONT_SYMBOLS,
    GAP,
    GLOSSARY_BODY_SIZE,
    GLOSSARY_GAP,
    GLOSSARY_INNER,
    GLOSSARY_LINE,
    GLOSSARY_TITLE_SIZE,
    GRID_COLS,
    H,
    HEADER_H,
    INTEGER,
    KIND_COLOR,
    KIND_WEIGHT,
    LEFT_W,
    M,
    MAX_PAGE_H,
    MAX_PARTS,
    MECHANIC,
    MECHANIC_RE,
    MECHANIC_TERMS,
    PARAM_RE,
    PATH_LABELS,
    PUNCT_ONLY,
    QUOTE,
    QUOTE_RE,
    RANK_ICON_DIR,
    RIGHT_W,
    RIGHT_X,
    ROW_GAP,
    SECTION_GAP,
    SECTION_HEAD_H,
    SECTION_TOP,
    SKILL_BOTTOM,
    SKILL_PAD,
    SKILL_SPLIT_W,
    SKILL_TITLE_SIZE,
    SKILL_TITLE_STEP,
    STATS_GAP,
    STATS_H,
    STATS_ROW,
    TAG_LABELS,
    TAG_RE,
    TYPE_FALLBACKS,
    TYPE_ICONS,
    TYPE_ORDER,
    UI_LABELS,
    VALUE,
    VALUE_KINDS,
    W,
    WEIGHT_BOLD,
    WEIGHT_REGULAR,
    WEIGHT_SEMI,
    _font_cache,
)
from hsr_cards.renderer.nanoka.skills.models import (
    GlossaryTerm,
    Piece,
    RankRow,
    SkillData,
    SkillGroup,
    SkillPanel,
    SkillRow,
    SkillSections,
    SkillTable,
    SkillsCardResult,
)
from hsr_cards.renderer.nanoka.skills.header import (
    art_panel,
    bonus_icon_name,
    draw_bonus_panel,
    draw_footer,
    draw_identity,
    draw_stat_panel,
    fit,
    footer_version,
    format_stat_value,
    header,
    header_art,
    page_background,
    scrim,
    section_title,
    splash,
    stat_icon,
    stat_pair,
    trimmed_splash,
    ui,
    version_pill,
    version_text,
    wrap_locale,
)
from hsr_cards.renderer.nanoka.skills.preparation import (
    column_label,
    e0_cap,
    format_number,
    format_stance,
    glossary_terms,
    group_columns,
    group_source,
    iter_source_skills,
    level_pairs,
    normalize_breaks,
    plain,
    rank_rows,
    raw_number,
    skill_groups,
    skill_rows,
    sp_change_text,
    stance_parts,
    stance_text,
    stance_values,
    target_text,
    value_color,
    value_kind,
)
from hsr_cards.renderer.nanoka.skills.tables import (
    build_sections,
    build_tables,
    group_table,
    material_sections,
)
from hsr_cards.renderer.nanoka.skills.assets import (
    eidolon_icon,
    previous_eidolon_icon,
    previous_rank,
    rank_portrait,
    skill_icon,
)
from hsr_cards.renderer.nanoka.skills.typography import (
    font_w,
    title_font,
    title_runs,
)
from hsr_cards.renderer.nanoka.skills.text import (
    _runs_to_pieces,
    desc_tokens,
    description_tokens,
    draw_lines,
    draw_text_runs,
    eidolon_tokens,
    glossary_tokens,
    layout_lines,
    measure_lines,
    measure_runs,
    measure_text_mixed,
    plain_leaf,
    plain_tokens,
    split_lines,
    text_units,
    trim_blank_lines,
)
from hsr_cards.renderer.nanoka.skills.cards import (
    eidolon_card,
    glossary_block,
    measure_eidolon_card,
    measure_glossary,
    measure_skill_card,
    measure_skill_panel,
    meta_label,
    skill_card,
    skill_header,
    skill_text_width,
    skill_title_lines,
    skill_title_width,
    stat_value,
    stats_block,
)
from hsr_cards.renderer.nanoka.skills.decorations import (
    change_badge,
    change_overlay,
)
from hsr_cards.renderer.nanoka.skills.layout import (
    _chunk_lines,
    best_section_layout,
    body_sizes,
    closest_cut,
    distribute_even,
    eidolon_heights,
    is_large_frame,
    masonry_columns,
    plan_page,
    safe_cuts,
    section_layout,
    sentence_cuts,
    skill_sections,
    slot_groups,
    split_group,
)
from hsr_cards.renderer.nanoka.skills.rendering import (
    render_eidolon_page,
    render_full,
    render_skill_page,
    render_summary,
)
from hsr_cards.services.skills import (
    build_comparison_data,
    build_skill_data,
    build_skills_card,
    load_data,
)
from hsr_cards.renderer.nanoka.skills.comparison import (
    _plain_runs,
    _runs_with_added,
    group_locale,
    mark_skill_diff,
)
from hsr_cards.renderer.nanoka.skills.cli import (
    build,
    main,
)
from hsr_cards.renderer.nanoka.character_info import BG
from pydantic import BaseModel
from hsr_cards.renderer.nanoka.data import CharacterData
from hsr_cards.nanoka.models import CharacterRank
from hsr_cards.nanoka.models import CharacterSkill
from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import FIRE
from pydantic import Field
from hsr_cards.renderer.nanoka.character_info import GOLD
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import PURPLE
from pathlib import Path
from hsr_cards.renderer.nanoka.data import RenderedCardCache
from hsr_cards.nanoka.models import SkillExtra
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import aggregate
import argparse
from hsr_cards.renderer.nanoka.character_info import asset
import asyncio
from hsr_cards.renderer.nanoka.character_info import bonus_stats
from hsr_cards.renderer.nanoka.character_info import clean_localized
from hsr_cards.renderer.nanoka.character_info import composite_panel
from dataclasses import dataclass
from hsr_cards.renderer.nanoka.diff import diff_runs
from dataclasses import field
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import format_bonus
import json
from hsr_cards.renderer.nanoka.data import load_character
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.character_info import make_star
from hsr_cards.renderer.nanoka.character_info import material_name
import math
from hsr_cards.renderer.nanoka.character_info import max_stats
from hsr_cards.renderer.nanoka.data import prime_assets
from hsr_cards.renderer.nanoka.character_info import radial
from hsr_cards.renderer.nanoka.data import rank_icon_relative
from hsr_cards.renderer.nanoka.data import rank_texture_relative
import re
from hsr_cards.renderer.nanoka.character_info import skill_materials
import sys
from hsr_cards.renderer.nanoka.character_info import wrap

if __name__ == '__main__':
    main()
