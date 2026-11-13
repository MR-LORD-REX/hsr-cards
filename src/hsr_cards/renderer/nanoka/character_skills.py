from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from ...nanoka.models import CharacterRank, CharacterSkill, SkillExtra
from .data import (
    CharacterData,
    RenderedCardCache,
    load_character,
    prime_assets,
    rank_icon_relative,
    rank_texture_relative,
)
from .diff import diff_runs
from .character_info import (
    BG,
    DIM,
    FIRE,
    GOLD,
    LINE,
    MUTED,
    PURPLE,
    TEXT,
    aggregate,
    bonus_stats,
    format_bonus,
    max_stats,
    asset,
    clean_localized,
    composite_panel,
    font,
    load_webp,
    make_star,
    material_name,
    radial,
    skill_materials,
    wrap,
)

W, H = 1920, 1350
RANK_ICON_DIR: Path | None = None  # legacy hook; the SDK passes rank art via SkillData
M = 58
GAP = 16
HEADER_H = 408
SECTION_TOP = HEADER_H + 26
CONTENT_TOP = SECTION_TOP + 46
BOTTOM_RESERVE = 58
EID_W = 452
LEFT_W = W - M * 2 - EID_W - GAP
RIGHT_X = M + LEFT_W + GAP
RIGHT_W = EID_W
ROW_GAP = 12
EID_GAP = 10
SECTION_GAP = 26
SECTION_HEAD_H = 50
GRID_COLS = (2,)

SKILL_TITLE_SIZE = 21
SKILL_TITLE_STEP = 25
SKILL_PAD = 14
SKILL_BOTTOM = 16
EID_TITLE_SIZE = 18
EID_TITLE_STEP = 21
EID_PAD = 14
EID_BOTTOM = 14

STATS_ROW = 20
STATS_H = STATS_ROW * 3 + 10
STATS_GAP = 12
GLOSSARY_GAP = 10
GLOSSARY_INNER = 10
GLOSSARY_TITLE_SIZE = 14
GLOSSARY_BODY_SIZE = 14
GLOSSARY_LINE = 19
DESC_SPLIT_H = 240
DESC_TARGET_H = 150
MAX_PARTS = 5
SKILL_SPLIT_W = 660

CARD_FILL = (25, 20, 40, 242)
CARD_EDGE = (255, 255, 255, 34)
BODY = (226, 219, 241, 255)
BODY_SOFT = (205, 196, 224, 255)
VALUE = (247, 197, 119, 255)
INTEGER = (126, 226, 222, 255)
DECIMAL = (201, 180, 255, 255)
QUOTE = (194, 222, 255, 255)
MECHANIC = (188, 241, 202, 255)
EIDOLON_VALUE = (226, 188, 255, 255)
DASH = "\u2013"

ELEMENT_LABELS = {
    "en": {
        "physical": "Physical", "fire": "Fire", "ice": "Ice", "thunder": "Lightning",
        "wind": "Wind", "quantum": "Quantum", "imaginary": "Imaginary",
    },
    "zh": {
        "physical": "\u7269\u7406", "fire": "\u706b", "ice": "\u51b0", "thunder": "\u96f7",
        "wind": "\u98ce", "quantum": "\u91cf\u5b50", "imaginary": "\u865a\u6570",
    },
    "ja": {
        "physical": "\u7269\u7406", "fire": "\u708e", "ice": "\u6c37", "thunder": "\u96f7",
        "wind": "\u98a8", "quantum": "\u91cf\u5b50", "imaginary": "\u865a\u6570",
    },
    "ko": {
        "physical": "\ubb3c\ub9ac", "fire": "\ud654\uc5fc", "ice": "\uc5bc\uc74c", "thunder": "\ubc88\uac1c",
        "wind": "\ubc14\ub78c", "quantum": "\uc591\uc790", "imaginary": "\ud5c8\uc218",
    },
}
PATH_LABELS = {
    "en": {
        "warlock": "Nihility", "knight": "Preservation", "rogue": "The Hunt",
        "mage": "Erudition", "shaman": "Abundance", "warrior": "Destruction",
        "memory": "Remembrance", "elation": "Elation",
    },
    "zh": {
        "warlock": "\u865a\u65e0", "knight": "\u5b58\u62a4", "rogue": "\u5de1\u730e", "mage": "\u667a\u8bc6",
        "shaman": "\u4e30\u9976", "warrior": "\u6bc1\u706d", "memory": "\u8bb0\u5fc6", "elation": "\u6b22\u6109",
    },
    "ja": {
        "warlock": "\u865a\u7121", "knight": "\u5b58\u8b77", "rogue": "\u5de1\u731f", "mage": "\u77e5\u6075",
        "shaman": "\u8c4a\u7a70", "warrior": "\u58ca\u6ec5", "memory": "\u8a18\u61b6", "elation": "\u6b61\u559c",
    },
    "ko": {
        "warlock": "\ud5c8\ubb34", "knight": "\ubcf4\uc874", "rogue": "\uc218\ub0a5", "mage": "\uc9c0\uc2dd",
        "shaman": "\ud48d\uc694", "warrior": "\ud30c\uad34", "memory": "\uae30\uc5b5", "elation": "\ud658\ud76c",
    },
}
UI_LABELS = {
    "en": {
        "header": "CHARACTER SKILLS", "skills": "COMBAT SKILLS", "eidolons": "EIDOLONS",
        "skills_sub": "DEFAULT VALUES  \u00b7  (#n) = TABLE COLUMN",
        "eidolons_sub": "E1 - E6  \u00b7  FIXED VALUES",
        "footer": "SKILLS / EIDOLONS", "passive": "PASSIVE",
        "memosprite": "MEMOSPRITE SKILLS",
        "energy": "Energy", "toughness": "Toughness", "sp": "SP Change",
        "base_stats": "BASIC STATS", "base_hp": "Base HP", "base_atk": "Base ATK",
        "base_def": "Base DEF", "base_spd": "Base SPD", "taunt": "Taunt",
        "max_energy": "Max Energy", "total_bonus": "TOTAL STAT BONUS",
        "levels": "DEFAULT LEVELS  \u00b7  BASIC ATK 6  \u00b7  SKILL / ULTIMATE / TALENT 10  \u00b7  MEMOSPRITE 6  \u00b7  TECHNIQUE 1  \u00b7  TABLES: ALL LEVELS",
    },
    "zh": {
        "header": "\u89d2\u8272\u6280\u80fd", "skills": "\u6218\u6597\u6280\u80fd", "eidolons": "\u661f\u9b42",
        "skills_sub": "\u9ed8\u8ba4\u6570\u503c  \u00b7  (#n) = \u8868\u683c\u5217",
        "eidolons_sub": "E1 - E6  \u00b7  \u56fa\u5b9a\u6570\u503c",
        "footer": "\u6280\u80fd / \u661f\u9b42", "passive": "\u88ab\u52a8",
        "base_stats": "\u57fa\u7840\u5c5e\u6027", "base_hp": "\u57fa\u7840\u751f\u547d", "base_atk": "\u57fa\u7840\u653b\u51fb",
        "base_def": "\u57fa\u7840\u9632\u5fa1", "base_spd": "\u57fa\u7840\u901f\u5ea6", "taunt": "\u5632\u8bbd",
        "max_energy": "\u6700\u5927\u80fd\u91cf", "total_bonus": "\u603b\u5c5e\u6027\u52a0\u6210",
        "memosprite": "\u5fc6\u7075\u6280\u80fd",
    },
    "ja": {
        "header": "\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u30b9\u30ad\u30eb", "skills": "\u6226\u95d8\u30b9\u30ad\u30eb", "eidolons": "\u661f\u9b42",
        "skills_sub": "\u65e2\u5b9a\u5024  \u00b7  (#n) = \u8868\u306e\u5217",
        "eidolons_sub": "E1 - E6  \u00b7  \u56fa\u5b9a\u5024",
        "footer": "\u30b9\u30ad\u30eb / \u661f\u9b42", "passive": "\u30d1\u30c3\u30b7\u30d6",
        "base_stats": "\u57fa\u790e\u30b9\u30c6\u30fc\u30bf\u30b9", "base_hp": "\u57fa\u790eHP", "base_atk": "\u57fa\u790e\u653b\u6483\u529b",
        "base_def": "\u57fa\u790e\u9632\u5fa1\u529b", "base_spd": "\u57fa\u790e\u901f\u5ea6", "taunt": "\u30bf\u30a6\u30f3\u30c8",
        "max_energy": "\u6700\u5927\u30a8\u30cd\u30eb\u30ae\u30fc", "total_bonus": "\u30b9\u30c6\u30fc\u30bf\u30b9\u30dc\u30fc\u30ca\u30b9",
        "memosprite": "\u30e1\u30e2\u30b9\u30d7\u30ea\u30c8\u30b9\u30ad\u30eb",
    },
    "ko": {
        "header": "\uce90\ub9ad\ud130 \uc2a4\ud0ac", "skills": "\uc804\ud22c \uc2a4\ud0ac", "eidolons": "\uc131\ud63c",
        "skills_sub": "\uae30\ubcf8\uac12  \u00b7  (#n) = \ud45c \uc5f4",
        "eidolons_sub": "E1 - E6  \u00b7  \uace0\uc815\uac12",
        "footer": "\uc2a4\ud0ac / \uc131\ud63c", "passive": "\ud328\uc2dc\ube0c",
        "base_stats": "\uae30\ubcf8 \uc2a4\ud0ef", "base_hp": "\uae30\ubcf8 HP", "base_atk": "\uae30\ubcf8 \uacf5\uaca9\ub825",
        "base_def": "\uae30\ubcf8 \ubc29\uc5b4\ub825", "base_spd": "\uae30\ubcf8 \uc18d\ub3c4", "taunt": "\ub3c4\ubc1c",
        "max_energy": "\ucd5c\ub300 \uc5d0\ub108\uc9c0", "total_bonus": "\uc804\uccb4 \uc2a4\ud0ef \ubcf4\ub108\uc2a4",
        "memosprite": "\uae30\uc5b5\uc758 \uc815\ub839 \uc2a4\ud0ac",
    },
}

TYPE_ORDER = {
    "Basic ATK": 0, "Skill": 1, "Ultimate": 2, "Talent": 3, "Technique": 4,
    "Assist Skill": 5, "Memosprite Skill": 6, "Memosprite Talent": 7,
    "Elation Skill": 8, "Aeonic Authority": 9, "Innate Trace": 10,
}
TYPE_ICONS = {
    "Basic ATK": "Normal", "Skill": "BP", "Ultimate": "Ultra", "Talent": "Passive",
    "Technique": "Maze", "Assist Skill": "Passive", "Elation Damage": "Normal",
    "Passive": "Passive", "Memosprite Skill": "Servant", "Memosprite Talent": "Passive",
}
TYPE_FALLBACKS = {
    "Normal": "Basic ATK", "BPSkill": "Skill", "Ultra": "Ultimate", "Talent": "Talent",
    "Maze": "Technique", "Assist": "Assist Skill", "ElationDamage": "Elation Damage",
    "Servant": "Memosprite Skill",
}
TAG_LABELS = {
    "SingleAttack": "Single Target", "AoEAttack": "AoE", "Bounce": "Bounce",
    "Blast": "Blast", "Support": "Support", "Impair": "Impair", "Restore": "Restore",
    "Defence": "Defense", "Enhance": "Enhance", "Passive": "Talent",
    "MazeAttack": "Technique", "Summon": "Summon", "Weaken": "Weaken",
    "Damage": "Damage", "Taunt": "Taunt", "Transform": "Transform",
}
PARAM_RE = re.compile(r"#(\d+)\[([^\]]+)\](%?)")
TAG_RE = re.compile(r"<[^>]+>")
QUOTE_RE = re.compile(r"<u>(.*?)</u>", re.S)
MECHANIC_TERMS = (
    "Follow-Up ATK", "Follow-up ATK", "DoT", "DMG over time", "Break Effect",
    "Effect Hit Rate", "Effect RES", "Ultimate", "Basic ATK", "Skill", "Talent",
    "Memosprite", "Speed", "Energy", "Toughness", "Weakness Break", "Super Break",
    "CRIT Rate", "CRIT DMG", "DEF", "ATK", "Max HP", "DMG",
)
MECHANIC_RE = re.compile(
    r'("([^"]+)")|\b(' + "|".join(re.escape(term) for term in sorted(MECHANIC_TERMS, key=len, reverse=True)) + r')\b',
    re.IGNORECASE,
)


@dataclass
class GlossaryTerm:
    key: str
    name: str
    desc: str
    params: list[float | int] = field(default_factory=list)


@dataclass
class SkillRow:
    index: int
    style: str
    first_display: str
    default_display: str
    default_value: float | int


@dataclass
class SkillGroup:
    key: str
    skill: CharacterSkill
    type_label: str
    tag_label: str
    target_label: str
    target_entries: list[tuple[str, str]]
    scope: str
    icon_code: str | None
    name: str
    desc: str
    raw_desc: str
    cap: int
    rows: list[SkillRow] = field(default_factory=list)
    level_rows: list[tuple[int, list[float | int]]] = field(default_factory=list)
    styles: dict[int, str] = field(default_factory=dict)
    table_columns: list[int] = field(default_factory=list)
    extras: list[GlossaryTerm] = field(default_factory=list)
    energy: str = DASH
    toughness: str = DASH
    sp_change: str = DASH
    diff_runs: list[tuple[str, str, tuple[int, int, int, int]]] | None = None
    change: str | None = None
    before: "SkillGroup | None" = None



@dataclass
class RankRow:
    key: str
    rank: CharacterRank
    name: str
    desc: str
    raw_desc: str
    params: list[tuple[int, str, str]] = field(default_factory=list)
    extras: list[GlossaryTerm] = field(default_factory=list)
    diff_runs: list[tuple[str, str, tuple[int, int, int, int]]] | None = None
    change: str | None = None
    before: "RankRow | None" = None


@dataclass
class SkillPanel:
    group: SkillGroup
    desc: str
    part: int = 1
    parts: int = 1
    extras: bool = True
    stats: bool = True
    lines: list[list[Piece]] | None = None


@dataclass
class SkillData:
    character_id: int
    locale: str
    version: str
    name: str
    description: str
    element_label: str
    path_label: str
    stars: int
    splash: Image.Image | None
    element_icon: Image.Image | None
    path_icon: Image.Image | None
    skill_icon_dir: Path
    rank_icon_dir: Path | None
    skills: list[SkillGroup]
    eidolons: list[RankRow]
    memosprite_name: str = ""
    memosprite_code: str = ""
    stats: dict[str, float] = field(default_factory=dict)
    bonuses: list[tuple[str, float, str]] = field(default_factory=list)
    sp_need: float = 0
    stats_before: dict[str, float] | None = None
    bonuses_before: list[tuple[str, float, str]] | None = None
    sp_need_before: float | None = None
    version_before: str = ""
    version_after: str = ""
    detail: Any = None
    items: dict[str, Any] = field(default_factory=dict)

    @property
    def comparison(self) -> bool:
        return bool(self.version_before and self.version_after)


class SkillTable(BaseModel):
    """One rich-message table with its section/dropdown label."""

    label: str
    table_id: str
    rows: list[list[str]] = Field(default_factory=list)


class SkillSections(BaseModel):
    """Key/value groups used beside each table in rich messages."""

    skills: dict[str, dict[str, str]] = Field(default_factory=dict)
    eidolons: dict[str, dict[str, str]] = Field(default_factory=dict)
    materials: dict[str, str] = Field(default_factory=dict)


class SkillsCardResult:
    """Rendered skills card plus rich-message table payloads.

    ``tables`` remains the backwards-compatible 2D array list. ``table_models``
    adds labels and stable ids, while ``sections`` carries the same labels
    shown on the card for direct use in Telegram rich messages.
    """

    def __init__(
        self,
        image: Image.Image,
        tables: list[list[list[str]]],
        dropdowns: dict[str, int],
        *,
        table_models: list[SkillTable] | None = None,
        sections: SkillSections | None = None,
    ):
        self.image = image
        self.tables = tables
        self.dropdowns = dropdowns
        self.table_models = table_models or [
            SkillTable(label=label, table_id=label, rows=tables[index])
            for label, index in dropdowns.items()
            if index < len(tables)
        ]
        self.sections = sections or SkillSections()

    def save(self, *args, **kwargs):
        return self.image.save(*args, **kwargs)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "tables": self.tables,
            "dropdowns": self.dropdowns,
            "table_models": [item.model_dump() for item in self.table_models],
            "sections": self.sections.model_dump(),
        }

def ui(data: SkillData, key: str) -> str:
    labels = UI_LABELS.get(data.locale, UI_LABELS["en"])
    return labels.get(key, UI_LABELS["en"].get(key, key))


def normalize_breaks(text: str) -> str:
    """Nanoka JSON stores paragraph breaks as literal backslash-n text."""
    return text.replace(chr(92)*2 + "n", chr(92) + "n")


def plain(text: str | None) -> str:
    if not text:
        return ""
    text = TAG_RE.sub("", normalize_breaks(text))
    text = PARAM_RE.sub(lambda match: f"#{match.group(1)}", text)
    # Block/box glyphs are intentionally redacted in the source; the text
    # faces on Windows have no glyph for them, so draw a visible placeholder.
    return re.sub(r"[ \t]+", " ", text).strip()


def format_number(value: float | int, style: str) -> str:
    """Format a Nanoka parameter using its template style.

    Nanoka templates encode percentages outside the parameter marker:
    ``#1[i]%``. The trailing ``%`` is part of ``style``, so it must survive
    parsing. Only percentage styles get a percent sign; integer and decimal
    styles are fixed values (``#2[i]`` turns, ``#3[f1]`` points) and are
    rendered bare.
    """
    percent = "%" in style
    base = style.replace("%", "")
    number = float(value) * (100 if percent else 1)
    if base == "i" and abs(number - round(number)) < 0.005:
        text = f"{round(number):d}"
    else:
        digits = 3 if abs(number * 1000 - round(number * 1000)) < 0.05 else 2
        text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    text = text or "0"
    return f"{text}%" if percent else text


def raw_number(value: float | int) -> str:
    """Return a Nanoka parameter at its native precision for table payloads."""
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.12g}"


def value_kind(style: str) -> str:
    """Classify a Nanoka style so percentages read differently from fixed values."""
    if "%" in style:
        return "percent"
    return "integer" if style.replace("%", "") == "i" else "decimal"


def value_color(style: str) -> tuple[int, int, int, int]:
    return KIND_COLOR[value_kind(style)]


def column_label(index: int) -> str:
    """Map a one-based parameter index to the table's A/B/C/D column label."""
    label = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def group_columns(group: SkillGroup) -> dict[int, str]:
    return {index: column_label(index) for index in group.table_columns}


def level_pairs(skill: CharacterSkill) -> list[tuple[int, list[float | int]]]:
    return [
        (int(entry.level if entry.level is not None else key), entry.param_list)
        for key, entry in sorted(
            skill.level.items(),
            key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0,
        )
        if entry.param_list
    ]


def e0_cap(skill: CharacterSkill, scope: str) -> int:
    if scope == "memosprite":
        return 6
    kind = skill.type or ""
    if kind == "Normal":
        return 6
    if kind in {"BPSkill", "Ultra", "Talent", "Assist", "ElationDamage"}:
        return 10
    if kind == "Maze":
        return 1
    label = TYPE_FALLBACKS.get(kind, skill.type_name or "")
    if label in {"Memosprite Skill", "Memosprite Talent"}:
        return 6
    if label in {"Innate Trace", "Elation Skill"}:
        return 1
    return 10


def skill_rows(skill: CharacterSkill, scope: str) -> tuple[
    int,
    list[tuple[int, list[float | int]]],
    list[SkillRow],
    dict[int, str],
    list[int],
]:
    levels = level_pairs(skill)
    cap = e0_cap(skill, scope)
    if not levels:
        return cap, [], [], {}, []
    styles = {
        int(match.group(1)): match.group(2) + (match.group(3) or "")
        for match in PARAM_RE.finditer(skill.desc or "")
    }
    indices = sorted({int(match.group(1)) for match in PARAM_RE.finditer(skill.desc or "")})
    columns = list(range(1, max(len(params) for _, params in levels) + 1))
    selected = levels[0][1]
    for level, params in levels:
        if level <= cap:
            selected = params
    first = levels[0][1]
    rows = []
    for index in indices:
        if index - 1 >= len(selected):
            continue
        style = styles.get(index, "f1")
        rows.append(
            SkillRow(
                index=index,
                style=style,
                first_display=format_number(first[index - 1], style) if index - 1 < len(first) else "",
                default_display=format_number(selected[index - 1], style),
                default_value=selected[index - 1],
            )
        )
    return cap, levels, rows, styles, columns


def iter_source_skills(source: dict) -> list[CharacterSkill]:
    skills = []
    for key, raw in source.items():
        if isinstance(raw, CharacterSkill):
            skills.append(raw)
            continue
        payload = dict(raw)
        if "id" not in payload:
            payload["id"] = int(key) if str(key).isdigit() else 0
        skills.append(CharacterSkill.model_validate(payload))
    return skills


def group_source(detail, scope: str) -> dict:
    if scope == "memosprite":
        return (detail.memosprite or {}).get("skills") or {}
    return detail.skills or {}


def glossary_terms(raw) -> list[GlossaryTerm]:
    if not raw:
        return []
    items = raw.values() if isinstance(raw, dict) else raw
    result: list[GlossaryTerm] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if isinstance(item, SkillExtra):
            name_raw, desc_raw = item.name, item.desc
            params = list(item.param or item.param_list)
        elif isinstance(item, dict):
            name_raw, desc_raw = item.get("name"), item.get("desc")
            params = list(item.get("param") or item.get("param_list") or [])
        else:
            continue
        name = plain(name_raw)
        desc = desc_raw or ""
        if not name or not desc.strip():
            continue
        key = (name, desc)
        if key in seen:
            continue
        seen.add(key)
        result.append(GlossaryTerm(key=str(len(result)), name=name, desc=desc, params=params))
    return result


def sp_change_text(skill: CharacterSkill) -> str:
    if skill.bp_add is not None:
        return f"+{skill.bp_add}"
    need = skill.bp_need or 0
    if need > 0:
        return f"-{need}"
    return DASH


def target_text(skill: CharacterSkill) -> str:
    tag = skill.tag or ""
    if not tag:
        return ""
    if "/" in tag:
        labels = [TAG_LABELS.get(part.strip(), part.strip()) for part in tag.split("/") if part.strip()]
        return " / ".join(labels).upper()
    label = TAG_LABELS.get(tag, "")
    if not label and tag.startswith("Single"):
        label = "Single Target"
    return label.upper()


def stance_values(skill: CharacterSkill) -> list[float]:
    """Nanoka stores toughness in third-points; the UI shows whole points."""
    return [round(float(value) / 3, 2) for value in (skill.show_stance_list or []) if value]


def stance_parts(skill: CharacterSkill) -> list[tuple[str, float]]:
    values = stance_values(skill)
    if not values:
        return []
    tags = [part.strip() for part in (skill.tag or "").split("/") if part.strip()]
    labels = [TAG_LABELS.get(tag, tag) for tag in tags]
    if len(labels) == len(values) and all(labels):
        return list(zip(labels, values))
    if len(values) == 1:
        return [(TAG_LABELS.get(tags[0], target_text(skill).title()) if tags else "Toughness", values[0])]
    first = "Blast" if "Blast" in tags else "Single Target"
    labels = [first, "AoE"] if len(values) > 1 else [first]
    labels.extend("AoE" for _ in values[2:])
    return list(zip(labels[:len(values)], values))


def format_stance(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


def stance_text(skill: CharacterSkill) -> str:
    parts = stance_parts(skill)
    if not parts:
        return DASH
    return " / ".join(
        f"{name}: {format_stance(value)}" if name else format_stance(value)
        for name, value in parts
    )


def skill_groups(detail) -> list[SkillGroup]:
    merged: dict[tuple[str, str], tuple[CharacterSkill, str]] = {}
    for scope in ("character", "memosprite"):
        for skill in iter_source_skills(group_source(detail, scope)):
            if skill.type == "MazeNormal":
                continue
            description = plain(skill.desc)
            if not description:
                continue
            label = TYPE_FALLBACKS.get(skill.type or "", skill.type_name or "Unknown")
            key = (label, plain(skill.name))
            existing = merged.get(key)
            if existing is None or len(description) > len(plain(existing[0].desc)):
                merged[key] = (skill, scope)
    groups = []
    for (label, _), (skill, scope) in merged.items():
        cap, levels, rows, styles, columns = skill_rows(skill, scope)
        entries = stance_parts(skill)
        target_entries = [] if entries else []
        groups.append(
            SkillGroup(
                key=str(skill.id),
                skill=skill,
                type_label=label.upper(),
                tag_label=TAG_LABELS.get(skill.tag or "", ""),
                target_label=target_text(skill),
                target_entries=target_entries,
                scope=scope,
                icon_code=TYPE_ICONS.get(label),
                name=plain(skill.name) or str(skill.id),
                desc=plain(skill.desc),
                raw_desc=skill.desc or "",
                cap=cap,
                rows=rows,
                level_rows=levels,
                styles=styles,
                table_columns=columns,
                extras=glossary_terms(skill.extra),
                energy=str(skill.sp_base) if skill.sp_base is not None else DASH,
                toughness=stance_text(skill),
                sp_change=sp_change_text(skill),
            )
        )
    return sorted(
        groups,
        key=lambda group: (
            TYPE_ORDER.get(TYPE_FALLBACKS.get(group.skill.type or "", group.skill.type_name or ""), 99),
            0 if group.scope == "character" else 1,
            group.name,
        ),
    )


def rank_rows(rank_map: dict) -> list[RankRow]:
    result = []
    for key, raw in sorted(
        rank_map.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0
    ):
        if isinstance(raw, CharacterRank):
            rank = raw
        else:
            payload = dict(raw)
            if "id" not in payload:
                payload["id"] = int(key) if str(key).isdigit() else 0
            rank = CharacterRank.model_validate(payload)
        styles = {
            int(match.group(1)): match.group(2) + (match.group(3) or "")
            for match in PARAM_RE.finditer(rank.desc or "")
        }
        params = []
        for index, value in enumerate(rank.param_list, start=1):
            style = styles.get(index, "i")
            params.append((index, format_number(value, style), style))
        result.append(
            RankRow(
                key=key,
                rank=rank,
                name=plain(rank.name) or key,
                desc=plain(rank.desc),
                raw_desc=rank.desc or "",
                params=params,
                extras=glossary_terms(rank.extra),
            )
        )
    return result


def group_table(group: SkillGroup) -> list[list[str]] | None:
    if not group.level_rows or not group.table_columns:
        return None
    comparison = group.before is not None and group.change is not None
    table = [["#"] + [column_label(index) for index in group.table_columns]]
    previous = {
        level: params for level, params in (group.before.level_rows if group.before else [])
    }
    for level, params in group.level_rows:
        row = [f"Lv.{level}"]
        old_params = previous.get(level, [])
        for index in group.table_columns:
            style = group.styles.get(index, "f1")
            if index - 1 >= len(params):
                row.append("")
                continue
            value = format_number(params[index - 1], style) if comparison else raw_number(params[index - 1])
            if not comparison:
                row.append(value)
                continue
            old_value = (
                format_number(old_params[index - 1], style)
                if index - 1 < len(old_params)
                else DASH
            )
            row.append(value if old_value == value else f"{old_value} \u2192 {value}")
        table.append(row)
    return table


def build_tables(data: SkillData) -> tuple[list[list[list[str]]], dict[str, int]]:
    tables: list[list[list[str]]] = []
    dropdowns: dict[str, int] = {}
    for group in data.skills:
        table = group_table(group)
        if not table:
            continue
        label = f"{group.type_label} \u00b7 {group.name}"
        if label in dropdowns:
            label = f"{label} \u00b7 {group.key}"
        dropdowns[label] = len(tables)
        tables.append(table)
    return tables, dropdowns


def material_sections(data: SkillData) -> dict[str, str]:
    """Rich-message totals for the two material panels on the info card."""
    detail = data.detail
    items = data.items
    ascension = aggregate(cost for stat in detail.stats.values() for cost in stat.cost)
    skills = skill_materials(detail)
    result = {}
    for label, costs in (("ascension", ascension), ("skills", skills)):
        result[f"{label}_credits"] = f"{next((cost.amount for cost in costs if cost.item_id == 2), 0):,}"
        for cost in costs:
            if cost.item_id == 2:
                continue
            name = material_name(items, cost.item_id, data.locale)
            result[f"{label}:{name}"] = f"x{cost.amount:,}"
    return result


def build_sections(data: SkillData) -> SkillSections:
    skills: dict[str, dict[str, str]] = {}
    for group in data.skills:
        label = f"{group.type_label} \u00b7 {group.name}"
        values = {
            "type": group.type_label,
            "target": group.target_label,
            "level": str(group.cap) if group.level_rows else ui(data, "passive"),
            "energy": group.energy,
            "toughness": group.toughness,
            "sp_change": group.sp_change,
            "description": group.desc,
        }
        if group.change:
            values["change"] = group.change
        skills[label] = values
    eidolons: dict[str, dict[str, str]] = {}
    for rank in data.eidolons:
        label = f"E{rank.key} \u00b7 {rank.name}"
        values = {"name": rank.name, "description": rank.desc}
        if rank.change:
            values["change"] = rank.change
        eidolons[label] = values
    return SkillSections(skills=skills, eidolons=eidolons, materials=material_sections(data))

def page_background(width: int, height: int) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), BG)
    canvas.alpha_composite(radial((1500, 1300), (116, 68, 205), 0.30), (-520, -560))
    canvas.alpha_composite(radial((1200, 1200), (217, 87, 57), 0.16), (width - 700, -460))
    return canvas


def wrap_locale(draw, text: str, fnt, width: int, locale: str) -> list[str]:
    if locale not in ("zh", "ja"):
        return wrap(draw, text, fnt, width)
    lines = []
    for paragraph in text.replace("\\n", "\n").split("\n"):
        line = ""
        for char in paragraph:
            candidate = line + char
            if draw.textlength(candidate, font=fnt) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = char
        if line:
            lines.append(line)
    return lines


def fit(draw, text: str, fnt, width: int) -> str:
    if draw.textlength(text, font=fnt) <= width:
        return text
    suffix = "..."
    while text and draw.textlength(text + suffix, font=fnt) > width:
        text = text[:-1]
    return text.rstrip() + suffix


def version_text(data: SkillData) -> str:
    if data.comparison:
        return f"v{data.version_before} \u2192 v{data.version_after}  /  {data.locale.upper()}"
    return f"v{data.version}  /  {data.locale.upper()}"


def version_pill(canvas, draw, data: SkillData, width: int, y: int = 20):
    text = version_text(data)
    fnt = font(15, bold=True, locale=data.locale)
    text_w = draw.textlength(text, font=fnt)
    x0 = width - M - text_w - 32
    composite_panel(canvas, (x0, y, width - M, y + 40), 20, (19, 13, 33, 246), (255, 255, 255, 66))
    draw.text((x0 + 16, y + 9), text, font=fnt, fill=TEXT)


def trimmed_splash(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A").point(lambda value: 255 if value > 34 else 0)
    box = alpha.getbbox()
    if box:
        left, top, right, bottom = box
        image = image.crop(
            (
                max(0, left - 24),
                max(0, top - 16),
                min(image.width, right + 24),
                min(image.height, bottom + 16),
            )
        )
    return image


def splash(canvas: Image.Image, data: SkillData, x: int, y: int, target_h: int) -> int:
    if not data.splash:
        return 0
    image = trimmed_splash(data.splash)
    scale = target_h / image.height
    resized = image.resize((round(image.width * scale), target_h), Image.Resampling.LANCZOS)
    canvas.alpha_composite(radial((850, 850), (246, 172, 87, 0.20)), (x - 70, y - 10))
    canvas.alpha_composite(resized, (x, y))
    return resized.width


def art_panel(data: SkillData, width: int, height: int) -> tuple[int, int, int, int]:
    """Left header region that hosts the splash behind the identity text."""
    return 0, 0, 812, height


def scrim(size: tuple[int, int], horizontal: bool) -> Image.Image:
    """Linear fade used to keep identity text readable over character art."""
    w, h = size
    layer = Image.new("RGBA", (max(1, w // 4), max(1, h // 4)), (0, 0, 0, 0))
    pixels = layer.load()
    small_w, small_h = layer.size
    for y in range(small_h):
        for x in range(small_w):
            if horizontal:
                t = x / max(small_w - 1, 1)
                alpha = round(226 * (1 - t) ** 0.85)
            else:
                t = y / max(small_h - 1, 1)
                alpha = round(180 * t ** 1.1)
            pixels[x, y] = (12, 8, 23, alpha)
    return layer.resize((w, h), Image.Resampling.BILINEAR)


def header_art(canvas, data: SkillData, width: int, height: int) -> None:
    if not data.splash:
        return
    image = trimmed_splash(data.splash)
    target_h = height + 18
    scale = target_h / image.height
    resized = image.resize((round(image.width * scale), target_h), Image.Resampling.LANCZOS)
    # Sit the art in the gap between the identity text and the stats panel
    # instead of flush against the left edge, where it collided with the copy.
    max_width = 470
    if resized.width > max_width:
        ratio = max_width / resized.width
        resized = resized.resize((max_width, round(resized.height * ratio)), Image.Resampling.LANCZOS)
    art_x = 812 - resized.width
    art_y = height - resized.height + 26
    canvas.alpha_composite(radial((700, 700), (246, 172, 87, 0.18)), (art_x + 20, art_y + 40))
    canvas.alpha_composite(resized, (art_x, art_y))
    canvas.alpha_composite(scrim((780, height), horizontal=True), (0, 0))
    canvas.alpha_composite(scrim((780, height), horizontal=False), (0, 0))


def stat_icon(data: SkillData, name: str | None, size: int = 18) -> Image.Image | None:
    if not name:
        return None
    return load_webp(data.skill_icon_dir / name, (size, size))


def draw_identity(canvas, draw, data: SkillData, width: int, height: int) -> None:
    text_w = 556
    title = data.name.upper() if data.locale == "en" else data.name
    title_size = 48
    while title_size > 34 and draw.textlength(
        title, font=font(title_size, bold=True, display=True, locale=data.locale)
    ) > text_w:
        title_size -= 2
    if any(ord(char) > 127 for char in title):
        title_font = font_w(title_size, WEIGHT_BOLD, data.locale, title)
    else:
        title_font = font(title_size, bold=True, display=True, locale=data.locale)
    y = 72
    for line in wrap_locale(draw, title, title_font, text_w, data.locale)[:2]:
        draw.text((M, y), line, font=title_font, fill=TEXT)
        y += round(title_size * 1.12)
    y += 8
    for index in range(data.stars):
        make_star(canvas, M + 12 + index * 25, y + 9, 10, GOLD)
    y += 29
    tag_x = M
    for label, icon, color in (
        (data.element_label.upper(), data.element_icon, FIRE),
        (data.path_label.upper(), data.path_icon, PURPLE),
    ):
        fnt = font(12, bold=True, locale=data.locale)
        tag_w = draw.textlength(label, font=fnt) + 40
        composite_panel(canvas, (tag_x, y, tag_x + tag_w, y + 30), 15, (*color[:3], 42), (*color[:3], 132))
        if icon:
            canvas.alpha_composite(icon.resize((20, 20), Image.Resampling.LANCZOS), (round(tag_x) + 10, round(y) + 5))
            draw.text((tag_x + 37, y + 7), label, font=fnt, fill=color)
        else:
            draw.text((tag_x + 18, y + 7), label, font=fnt, fill=color)
        tag_x += tag_w + 9
    if data.description:
        desc_font = font(15, locale=data.locale)
        y += 42
        for line in wrap_locale(draw, data.description, desc_font, text_w, data.locale)[:3]:
            draw_text_runs(draw, line, M, y, 15, WEIGHT_REGULAR, BODY_SOFT, data.locale)
            y += 20

def format_stat_value(value: float, *, comma: bool = False) -> str:
    if comma:
        return f"{value:,.0f}"
    return f"{value:g}"


def stat_pair(value: str, previous: str | None) -> str:
    if previous is None or previous == value:
        return value
    return f"{previous} \u2192 {value}"


def draw_stat_panel(canvas, draw, data: SkillData, x: int, y: int, width: int, height: int) -> None:
    composite_panel(canvas, (x, y, x + width, y + height), 20, (19, 14, 33, 236), (255, 255, 255, 40))
    draw.text((x + 22, y + 16), ui(data, "base_stats"), font=font_w(12, WEIGHT_BOLD, data.locale), fill=PURPLE)
    draw.text(
        (x + width - 22 - draw.textlength("LV. 80", font=font_w(11, WEIGHT_SEMI, data.locale)), y + 17),
        "LV. 80",
        font=font_w(11, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
    draw.line((x + 22, y + 42, x + width - 22, y + 42), fill=LINE, width=1)
    stats = data.stats
    before = data.stats_before
    specs = [
        ("hp", ui(data, "base_hp"), "IconMaxHP.webp", True),
        ("atk", ui(data, "base_atk"), "IconAttack.webp", True),
        ("def", ui(data, "base_def"), "IconDefence.webp", True),
        ("spd", ui(data, "base_spd"), "IconSpeed.webp", False),
        ("aggro", ui(data, "taunt"), None, False),
        (None, ui(data, "max_energy"), None, False),
    ]
    rows = max(1, len(specs))
    row_h = (height - 52) / rows
    for index, (key, label, icon_name, comma) in enumerate(specs):
        ry = y + 50 + index * row_h
        if key is None:
            value = format_stat_value(data.sp_need, comma=False)
            previous_value = (
                format_stat_value(data.sp_need_before, comma=False)
                if data.sp_need_before not in (None, data.sp_need)
                else None
            )
        else:
            value = format_stat_value(stats.get(key, 0), comma=comma)
            previous_value = (
                format_stat_value(before[key], comma=comma)
                if before is not None and before.get(key) != stats.get(key)
                else None
            )
        icon = stat_icon(data, icon_name, 18)
        text_x = x + 24
        if icon:
            canvas.alpha_composite(icon, (x + 22, round(ry) - 2))
            text_x = x + 48
        draw.text((text_x, ry), label, font=font_w(13, WEIGHT_SEMI, data.locale), fill=MUTED)
        text = stat_pair(value, previous_value)
        value_font = font_w(14, WEIGHT_BOLD, data.locale)
        value_w = draw.textlength(text, font=value_font)
        value_color = GOLD if previous_value else TEXT
        draw.text((x + width - 22 - value_w, ry - 1), text, font=value_font, fill=value_color)
        if index < rows - 1:
            draw.line((x + 22, ry + row_h - 7, x + width - 22, ry + row_h - 7), fill=(255, 255, 255, 18), width=1)
        if previous_value:
            change_overlay(canvas, (x + 12, ry - 6, x + width - 12, ry + row_h - 4), radius=8)


def bonus_icon_name(label: str) -> str | None:
    return {
        "HP": "IconMaxHP.webp",
        "ATK": "IconAttack.webp",
        "DEF": "IconDefence.webp",
        "SPD": "IconSpeed.webp",
        "CRIT Rate": "IconCriticalChance.webp",
        "CRIT DMG": "IconCriticalDamage.webp",
        "Fire DMG Boost": "IconFireAddedRatio.webp",
        "Ice DMG Boost": "IconIceAddedRatio.webp",
        "Wind DMG Boost": "IconWindAddedRatio.webp",
        "Lightning DMG Boost": "IconThunderAddedRatio.webp",
        "Physical DMG Boost": "IconPhysicalAddedRatio.webp",
        "Quantum DMG Boost": "IconQuantumAddedRatio.webp",
        "Imaginary DMG Boost": "IconImaginaryAddedRatio.webp",
    }.get(label)
def draw_bonus_panel(canvas, draw, data: SkillData, x: int, y: int, width: int, height: int) -> None:


    composite_panel(canvas, (x, y, x + width, y + height), 20, (19, 14, 33, 236), (255, 255, 255, 40))
    draw.text((x + 22, y + 16), ui(data, "total_bonus"), font=font_w(12, WEIGHT_BOLD, data.locale), fill=PURPLE)
    subtitle = "MINOR TRACES"
    draw.text(
        (x + width - 22 - draw.textlength(subtitle, font=font_w(10, WEIGHT_SEMI, data.locale)), y + 17),
        subtitle,
        font=font_w(10, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
    draw.line((x + 22, y + 42, x + width - 22, y + 42), fill=LINE, width=1)

    old = {label: (value, property_type) for label, value, property_type in (data.bonuses_before or [])}
    labels = [label for label, _, _ in data.bonuses]
    labels.extend(label for label in old if label not in labels)
    rows = labels[:6]
    columns = 3
    tile_gap = 12
    inner_w = width - 44
    tile_w = (inner_w - tile_gap * (columns - 1)) / columns
    tile_h = 86
    for index, label in enumerate(rows):
        col = index % columns
        row = index // columns
        bx = x + 22 + col * (tile_w + tile_gap)
        by = y + 56 + row * (tile_h + 10)
        current = next(
            ((value, property_type) for name, value, property_type in data.bonuses if name == label),
            None,
        )
        previous = old.get(label)
        changed = current is None or (previous is not None and previous[0] != current[0])
        tile_fill = (142, 216, 168, 20) if changed else (255, 255, 255, 16)
        tile_edge = (142, 216, 168, 64) if changed else (255, 255, 255, 24)
        composite_panel(canvas, (bx, by, bx + tile_w, by + tile_h), 14, tile_fill, tile_edge)
        icon = stat_icon(data, bonus_icon_name(label), 16)
        label_x = bx + 14
        if icon:
            canvas.alpha_composite(icon, (round(bx + 12), round(by + 12)) )
            label_x = bx + 34
        draw.text(
            (label_x, by + 12),
            fit(draw, label.upper(), font_w(10, WEIGHT_SEMI, data.locale), tile_w - (label_x - bx) - 12),
            font=font_w(10, WEIGHT_SEMI, data.locale),
            fill=MUTED,
        )
        if current is None:
            value_text = format_bonus(*previous)
            value_color = (224, 150, 164, 255)
        else:
            value_text = format_bonus(*current)
            value_color = TEXT
        draw.text((bx + 14, by + 34), value_text, font=font_w(24, WEIGHT_BOLD, data.locale, value_text), fill=value_color)
        if current is not None and previous is not None and previous[0] != current[0]:
            draw.text(
                (bx + 14, by + tile_h - 22),
                f"was {format_bonus(*previous)}",
                font=font_w(9, WEIGHT_SEMI, data.locale),
                fill=(224, 150, 164, 230),
            )


def header(canvas, draw, data: SkillData, width: int, height: int):
    draw.rectangle((0, 0, width, height), fill=(12, 8, 23, 255))
    header_art(canvas, data, width, height)
    draw.line((M, 64, width - M, 64), fill=LINE, width=1)
    header_label = ui(data, "header")
    if data.comparison:
        header_label = f"{header_label}  /  VERSION COMPARISON"
    draw.text(
        (M, 27),
        f"NANOKA / HSR  /  {header_label}",
        font=font(14, bold=True, locale=data.locale),
        fill=MUTED,
    )
    version_pill(canvas, draw, data, width)
    draw_identity(canvas, draw, data, width, height)

    stats_x = 828
    stats_w = 456
    bonus_x = stats_x + stats_w + 18
    bonus_w = width - M - bonus_x
    panel_y = 82
    panel_h = height - panel_y - 48
    draw_stat_panel(canvas, draw, data, stats_x, panel_y, stats_w, panel_h)
    draw_bonus_panel(canvas, draw, data, bonus_x, panel_y, bonus_w, panel_h)

    if data.comparison:
        draw.text(
            (M, height - 26),
            f"OLD v{data.version_before} struck/removed  \u00b7  NEW v{data.version_after} highlighted",
            font=font(9, bold=True, locale=data.locale),
            fill=DIM,
        )
    else:
        draw.text(
            (M, height - 26),
            ui(data, "levels"),
            font=font(9, bold=True, locale=data.locale),
            fill=DIM,
        )

def section_title(draw, x: int, y: int, title: str, subtitle: str, width: int, locale: str, size: int = 20) -> int:
    draw.rectangle((x, y + 6, x + 24, y + 10), fill=PURPLE)
    draw.text((x + 34, y - 4), title, font=font(size, bold=True, locale=locale), fill=PURPLE)
    if subtitle:
        sub = font(10, bold=True, locale=locale)
        sub_w = draw.textlength(subtitle, font=sub)
        draw.text((x + width - sub_w, y + 1), subtitle, font=sub, fill=DIM)
    draw.line((x, y + 33, x + width, y + 33), fill=LINE, width=1)
    return y + 33


def skill_icon(data: SkillData, group: SkillGroup, size: int) -> Image.Image | None:
    code = data.memosprite_code if group.scope == "memosprite" else str(data.character_id)
    suffix = group.icon_code or ""
    if group.scope == "memosprite" and suffix == "Passive":
        suffix = "ServantPassive"
    elif group.scope == "memosprite":
        suffix = "Servant"
    if not code or not suffix:
        return None
    candidates = (f"SkillIcon_{code}_{suffix}.webp", f"SkillIcon_{code}_Servant.webp", f"SkillIcon_{code}_Servant01.webp")
    for name in candidates:
        image = load_webp(data.skill_icon_dir / name, (size, size))
        if image:
            return image
    return None


def rank_portrait(path: Path, size: int) -> Image.Image | None:
    image = load_webp(path)
    if image is None:
        return None
    alpha = image.getchannel("A").point(lambda value: 255 if value > 30 else 0)
    box = alpha.getbbox()
    if box:
        image = image.crop(box)
    side = min(image.width, image.height)
    left = max(0, (image.width - side) // 2)
    top = max(0, round(image.height * 0.06))
    if top + side > image.height:
        top = image.height - side
    image = image.crop((left, max(0, top), left + side, max(0, top) + side))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def eidolon_icon(data: SkillData, rank: RankRow, size: int) -> Image.Image | None:
    # Nanoka points E3/E5 at the generic Ultra/Skill icons, so prefer real
    # rank textures when they were downloaded into the card cache.
    if data.rank_icon_dir:
        image = rank_portrait(data.rank_icon_dir / f"{data.character_id}_Rank_{rank.key}.webp", size)
        if image:
            return image
    candidates = [f"SkillIcon_{data.character_id}_Rank{rank.key}.webp"]
    stem = Path(rank.rank.icon or "").stem
    if stem:
        candidates.append(f"{stem}.webp")
    for name in candidates:
        image = load_webp(data.skill_icon_dir / name, (size, size))
        if image:
            return image
    return None


def previous_rank(data: SkillData, rank: RankRow) -> RankRow | None:
    keys = [item.key for item in data.eidolons]
    try:
        index = keys.index(rank.key)
    except ValueError:
        return None
    return data.eidolons[index - 1] if index > 0 else None


def previous_eidolon_icon(data: SkillData, rank: RankRow, size: int) -> Image.Image | None:
    """The previous eidolon's skill icon, shown top-left on each card.

    Nanoka only publishes Rank1/2/4/6 skill icons; E3 and E5 point at the
    generic Ultra/Skill icons. Reading the previous rank's own ``icon`` field
    keeps that mapping intact. E1 has no predecessor, so it falls back to the
    character's basic ATK icon.
    """
    before = previous_rank(data, rank)
    if before is not None:
        icon_name = Path(str(before.rank.icon or "")).stem
        candidates = [f"{icon_name}.webp"] if icon_name else []
        candidates.append(f"SkillIcon_{data.character_id}_Rank{before.key}.webp")
        for name in candidates:
            image = load_webp(data.skill_icon_dir / name, (size, size))
            if image:
                return image
        if data.rank_icon_dir:
            image = rank_portrait(
                data.rank_icon_dir / f"{data.character_id}_Rank_{before.key}.webp", size
            )
            if image:
                return image
    for suffix in ("Normal", "BP", "Ultra"):
        image = load_webp(
            data.skill_icon_dir / f"SkillIcon_{data.character_id}_{suffix}.webp", (size, size)
        )
        if image:
            return image
    return None

WEIGHT_REGULAR = "regular"
WEIGHT_SEMI = "semi"
WEIGHT_BOLD = "bold"
FONT_DIR = Path("C:/Windows/Fonts")
FONT_SEMI_FILE = FONT_DIR / "seguisb.ttf"
FONT_SYMBOLS = FONT_DIR / "seguisym.ttf"
FALLBACK_CHARS = set("\u266a\u2605\u221e\u25e6\u2606\u25a0\u2588")
_font_cache: dict[tuple[int, str, str], ImageFont.FreeTypeFont] = {}


def font_w(size: int, weight: str = WEIGHT_REGULAR, locale: str = "en", text: str = ""):
    key = (size, weight, locale)
    if locale == "en" and any(char in FALLBACK_CHARS for char in text) and FONT_SYMBOLS.exists():
        key = (size, weight, "symbols")
    if key in _font_cache:
        return _font_cache[key]
    if key[2] == "symbols":
        result = ImageFont.truetype(str(FONT_SYMBOLS), size)
    elif locale == "en" and weight == WEIGHT_SEMI and FONT_SEMI_FILE.exists():
        result = ImageFont.truetype(str(FONT_SEMI_FILE), size)
    else:
        result = font(size, bold=weight == WEIGHT_BOLD, locale=locale)
    _font_cache[key] = result
    return result

def title_font(size: int, data: SkillData, text: str = ""):
    if data.locale == "en" and any(char in FALLBACK_CHARS for char in text) and FONT_SYMBOLS.exists():
        return ImageFont.truetype(str(FONT_SYMBOLS), size)
    return font(size, bold=True, locale=data.locale)

def title_runs(draw, text: str, size: int, data: SkillData, x: int, y: int, fill=TEXT):
    base = font(size, bold=True, locale=data.locale)
    symbol = ImageFont.truetype(str(FONT_SYMBOLS), size) if FONT_SYMBOLS.exists() else base
    run = ""
    run_symbols = False
    cursor = float(x)
    for char in text:
        is_symbol = data.locale == "en" and char in FALLBACK_CHARS
        if run and is_symbol != run_symbols:
            face = symbol if run_symbols else base
            draw.text((cursor, y), run, font=face, fill=fill)
            cursor += draw.textlength(run, font=face)
            run = ""
        run += char
        run_symbols = is_symbol
    if run:
        face = symbol if run_symbols else base
        draw.text((cursor, y), run, font=face, fill=fill)
        cursor += draw.textlength(run, font=face)
    return cursor - x



KIND_WEIGHT = {
    "plain": WEIGHT_REGULAR,
    "dim": WEIGHT_REGULAR,
    "quote": WEIGHT_REGULAR,
    "mechanic": WEIGHT_REGULAR,
    "value": WEIGHT_SEMI,
    "percent": WEIGHT_SEMI,
    "integer": WEIGHT_SEMI,
    "decimal": WEIGHT_SEMI,
    "label": WEIGHT_SEMI,
    "title": WEIGHT_BOLD,
    "gloss": WEIGHT_REGULAR,
    "removed": WEIGHT_REGULAR,
    "added": WEIGHT_SEMI,
    "added_percent": WEIGHT_SEMI,
    "added_integer": WEIGHT_SEMI,
    "added_decimal": WEIGHT_SEMI,
    "added_value": WEIGHT_SEMI,
    "arrow": WEIGHT_REGULAR,
}
KIND_COLOR = {
    "plain": BODY,
    "dim": MUTED,
    "quote": QUOTE,
    "mechanic": MECHANIC,
    "value": VALUE,
    "percent": VALUE,
    "integer": INTEGER,
    "decimal": DECIMAL,
    "label": MUTED,
    "title": TEXT,
    "gloss": BODY_SOFT,
    "removed": (224, 150, 164, 255),
    "added": (142, 216, 168, 255),
    "added_percent": VALUE,
    "added_integer": INTEGER,
    "added_decimal": DECIMAL,
    "added_value": VALUE,
    "arrow": (150, 138, 175, 255),
}
VALUE_KINDS = {"value", "percent", "integer", "decimal"}
CHANGED_VALUE_KINDS = {"added_value", "added_percent", "added_integer", "added_decimal"}

PUNCT_ONLY = re.compile(r"^[,.;:!?%\u2026\)\]\}\u2019\u201d]+$")


@dataclass
class Piece:
    text: str
    color: tuple[int, int, int, int]
    weight: str
    strike: bool = False


def _runs_to_pieces(runs) -> list[Piece]:
    pieces: list[Piece] = []
    for text, kind, color in runs:
        if not text:
            continue
        pieces.append(
            Piece(text, color, KIND_WEIGHT.get(kind, WEIGHT_REGULAR), kind.startswith("removed"))
        )
    return pieces


def plain_tokens(text: str, *, keep_newlines: bool = True) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    text = TAG_RE.sub("", text).replace("\\n", "\n") if keep_newlines else TAG_RE.sub("", text).replace("\\n", " ")
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    position = 0

    def boundary(previous: str, following: str) -> bool:
        return bool(previous) and bool(following) and not previous.isspace() and not following.isspace()

    def emit(match_start: int, match_end: int, group: int):
        nonlocal position
        if match_start > position:
            tokens.extend(plain_leaf(text[position:match_start]))
        if match_start > 0 and boundary(text[match_start - 1], text[match_start]):
            tokens.append((" ", "plain", BODY))
        tokens.append((text[match_start:match_end], "quote" if group == 1 else "mechanic",
                       QUOTE if group == 1 else MECHANIC))
        if match_end < len(text) and boundary(text[match_end - 1], text[match_end]):
            tokens.append((" ", "plain", BODY))
        position = match_end

    for match in MECHANIC_RE.finditer(text):
        emit(match.start(), match.end(), 1 if match.group(1) else 3)
    if position < len(text):
        tokens.extend(plain_leaf(text[position:]))
    return tokens


def plain_leaf(text: str) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    parts = re.split(r"(\n|\\n)", text)
    result = []
    for part in parts:
        if part in ("\n", "\\n"):
            result.append(("\n", "plain", BODY))
        elif part:
            result.append((part, "plain", BODY))
    return result


def text_units(text: str, locale: str) -> list[tuple[str, bool]]:
    if not text:
        return []
    if locale in ("zh", "ja"):
        pattern = re.compile(r"\s+|[\u4e00-\u9fff\u3040-\u30ff]|[^\s\u4e00-\u9fff\u3040-\u30ff]+")
        tokens = pattern.findall(text)
    else:
        tokens = re.findall(r"\s+|[^\s]+", text)
    units: list[tuple[str, bool]] = []
    pending_space = False
    for token in tokens:
        if token.isspace():
            pending_space = True
            continue
        if units and PUNCT_ONLY.match(token):
            units[-1] = (units[-1][0] + token, units[-1][1])
            continue
        if units and token.startswith("(") and PUNCT_ONLY.match(token[1:] or "x"):
            units[-1] = (units[-1][0] + token, units[-1][1])
            continue
        units.append((token, pending_space))
        pending_space = False
    return units


def description_tokens(group: SkillGroup) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    if group.diff_runs is not None:
        return group.diff_runs
    return desc_tokens(group.raw_desc or group.desc or "", {row.index: row for row in group.rows}, VALUE, group_columns(group))


def desc_tokens(raw: str, by_id: dict[int, SkillRow], color, columns: dict[int, str] | None = None) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    raw = normalize_breaks(raw or "")
    position = 0
    for match in PARAM_RE.finditer(raw):
        if match.start() > position:
            tokens.extend(plain_tokens(raw[position:match.start()]))
        index = int(match.group(1))
        row = by_id.get(index)
        suffix = match.group(3) or ""
        if row is None:
            tokens.append((f"#{index}{suffix}", "value", color))
        else:
            prefix = " " if match.start() > 0 and not raw[match.start() - 1].isspace() else ""
            kind = value_kind(row.style)
            label = columns.get(index) if columns else None
            suffix_text = f" ({label})" if label else ""
            tokens.append((f"{prefix}{row.default_display}{suffix_text}", kind, KIND_COLOR[kind]))
        position = match.end()
    if position < len(raw):
        tokens.extend(plain_tokens(raw[position:]))
    return [token for token in tokens if token[0]]


def eidolon_tokens(rank: RankRow) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    raw = normalize_breaks(rank.raw_desc or rank.desc or "")
    by_id = {index: (display, style) for index, display, style in rank.params}
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    position = 0
    for match in PARAM_RE.finditer(raw):
        if match.start() > position:
            tokens.extend(plain_tokens(raw[position:match.start()]))
        index = int(match.group(1))
        prefix = " " if match.start() > 0 and not raw[match.start() - 1].isspace() else ""
        if index in by_id:
            display, style = by_id[index]
            kind = value_kind(style)
            tokens.append((f"{prefix}{display}", kind, KIND_COLOR[kind]))
        else:
            tokens.append((f"{prefix}#{index}{match.group(3) or ''}", "value", EIDOLON_VALUE))
        position = match.end()
    if position < len(raw):
        tokens.extend(plain_tokens(raw[position:]))
    return [token for token in tokens if token[0]]


def glossary_tokens(term: GlossaryTerm) -> list[tuple[str, str, tuple[int, int, int, int]]]:
    raw = normalize_breaks(term.desc or "")
    tokens: list[tuple[str, str, tuple[int, int, int, int]]] = []
    position = 0
    for match in PARAM_RE.finditer(raw):
        if match.start() > position:
            tokens.extend(plain_tokens(raw[position:match.start()]))
        index = int(match.group(1))
        style = match.group(2) + (match.group(3) or "")
        prefix = " " if match.start() > 0 and not raw[match.start() - 1].isspace() else ""
        if 1 <= index <= len(term.params):
            text = format_number(term.params[index - 1], style)
            kind = value_kind(style)
        else:
            text = f"#{index}"
            kind = "value"
        tokens.append((f"{prefix}{text}", kind, KIND_COLOR.get(kind, VALUE)))
        position = match.end()
    if position < len(raw):
        tokens.extend(plain_tokens(raw[position:]))
    return [token for token in tokens if token[0]]


def layout_lines(draw, runs, width: int, size: int, locale: str) -> list[list[Piece]]:
    lines: list[list[Piece]] = [[]]
    line_w = 0.0
    space_w = draw.textlength(" ", font=font_w(size, WEIGHT_REGULAR, locale, " "))

    def add_piece(piece: Piece, space_before: bool):
        nonlocal line_w
        if not piece.text:
            return
        # Diff runs arrive one token at a time, so punctuation can meet the
        # wrapping pass as a separate unit. Glue it to the preceding word
        # instead of rendering "Energy ." with a stray space.
        punctuation = bool(PUNCT_ONLY.fullmatch(piece.text)) or bool(
            piece.text.startswith("(") and PUNCT_ONLY.fullmatch(piece.text[1:] or "x")
        )
        if punctuation and lines[-1] and line_w > 0:
            previous = lines[-1][-1]
            previous.text += piece.text
            line_w += measure_text_mixed(draw, piece.text, size, piece.weight, locale)
            return
        unit_w = measure_text_mixed(draw, piece.text, size, piece.weight, locale)
        gap = space_w if space_before and line_w > 0 else 0.0
        if line_w > 0 and line_w + gap + unit_w > width + 0.5:
            lines.append([])
            line_w = 0.0
            gap = 0.0
        if gap:
            lines[-1].append(Piece(" ", piece.color, WEIGHT_REGULAR))
            line_w += gap
        lines[-1].append(piece)
        line_w += unit_w

    for text, kind, color in runs:
        if text == "\n":
            lines.append([])
            line_w = 0.0
            continue
        weight = KIND_WEIGHT.get(kind, WEIGHT_REGULAR)
        strike = kind.startswith("removed")
        if kind in VALUE_KINDS or kind in CHANGED_VALUE_KINDS:
            add_piece(Piece(text, color, weight, strike), True)
            continue
        for unit, space_before in text_units(text, locale):
            add_piece(Piece(unit, color, weight, strike), space_before or bool(lines[-1]))

    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    if len(lines) == 1 and not lines[0]:
        return []
    return lines


def measure_lines(lines: list[list[Piece]], line_h: int) -> int:
    return len(lines) * line_h


def trim_blank_lines(lines: list[list[Piece]]) -> list[list[Piece]]:
    while lines and not lines[0]:
        lines = lines[1:]
    while lines and not lines[-1]:
        lines = lines[:-1]
    return lines


def measure_text_mixed(draw, text: str, size: int, weight: str, locale: str) -> float:
    """Measure a string with the same per-run fallback faces used to draw it."""
    base = font_w(size, weight, locale)
    symbol = ImageFont.truetype(str(FONT_SYMBOLS), size) if FONT_SYMBOLS.exists() else base
    run = ""
    run_symbols = False
    width = 0.0
    for char in text:
        is_symbol = locale == "en" and char in FALLBACK_CHARS
        if run and is_symbol != run_symbols:
            face = symbol if run_symbols else base
            width += draw.textlength(run, font=face)
            run = ""
        run += char
        run_symbols = is_symbol
    if run:
        face = symbol if run_symbols else base
        width += draw.textlength(run, font=face)
    return width


def draw_text_runs(draw, text: str, x: int, y: int, size: int, weight: str, color, locale: str) -> float:
    """Draw a string while switching only the glyphs that need a fallback face."""
    base = font_w(size, weight, locale)
    symbol = ImageFont.truetype(str(FONT_SYMBOLS), size) if FONT_SYMBOLS.exists() else base
    run = ""
    run_symbols = False
    cursor = float(x)
    for char in text:
        is_symbol = locale == "en" and char in FALLBACK_CHARS
        if run and is_symbol != run_symbols:
            face = symbol if run_symbols else base
            draw.text((cursor, y), run, font=face, fill=color)
            cursor += draw.textlength(run, font=face)
            run = ""
        run += char
        run_symbols = is_symbol
    if run:
        face = symbol if run_symbols else base
        draw.text((cursor, y), run, font=face, fill=color)
        cursor += draw.textlength(run, font=face)
    return cursor


def draw_lines(draw, lines, x: int, y: int, size: int, line_h: int, locale: str = "en", max_lines: int | None = None) -> int:
    if max_lines is not None:
        lines = lines[:max_lines]
    for line_index, line in enumerate(lines):
        line_x = float(x)
        for piece in line:
            line_y = y + line_index * line_h
            if locale == "en" and any(char in FALLBACK_CHARS for char in piece.text):
                end_x = draw_text_runs(draw, piece.text, line_x, line_y, size, piece.weight, piece.color, locale)
            else:
                piece_font = font_w(size, piece.weight, locale, piece.text)
                draw.text((line_x, line_y), piece.text, font=piece_font, fill=piece.color)
                end_x = line_x + draw.textlength(piece.text, font=piece_font)
            if piece.strike and piece.text.strip():
                strike_y = line_y + round(size * 0.55)
                draw.line((line_x, strike_y, end_x, strike_y), fill=piece.color, width=max(1, size // 11))
            line_x = end_x
    return len(lines) * line_h


def split_lines(lines: list[list[Piece]], line_h: int, max_h: int) -> list[list[list[Piece]]]:
    total = len(lines) * line_h
    if total <= max_h or not lines:
        return [lines]
    parts = min(MAX_PARTS, max(2, math.ceil(total / DESC_TARGET_H)))
    per = math.ceil(len(lines) / parts)
    return [lines[index:index + per] for index in range(0, len(lines), per)]


def measure_runs(draw, runs, width: int, size: int, line_h: int, locale: str) -> tuple[int, int]:
    if not any(text.strip() for text, _, _ in runs if text != "\n"):
        return 0, 0
    lines = layout_lines(draw, runs, width, size, locale)
    return len(lines) * line_h, len(lines)

def skill_text_width(width: int) -> int:
    return width - SKILL_PAD * 2


def skill_title_width(width: int) -> int:
    return max(96, width - 214)


def skill_title_lines(draw, data: SkillData, group: SkillGroup, width: int) -> list[str]:
    return wrap_locale(
        draw, group.name, font(SKILL_TITLE_SIZE, bold=True, locale=data.locale), skill_title_width(width), data.locale
    )[:2]


def skill_header(draw, data: SkillData, group: SkillGroup, x: int, y: int, width: int) -> int:
    lines = skill_title_lines(draw, data, group, width)
    extra = max(0, len(lines) - 1)
    divider = y + 56 + extra * SKILL_TITLE_STEP
    return divider + 14


def meta_label(draw, data: SkillData, text: str, x: int, y: int, *, color=PURPLE) -> int:
    fnt = font_w(10, WEIGHT_SEMI, data.locale)
    width = draw.textlength(text, font=fnt) + 14
    draw.rounded_rectangle(
        (x, y, x + width, y + 17), radius=7,
        fill=(*color[:3], 26), outline=(*color[:3], 68), width=1,
    )
    draw.text((x + 7, y + 3), text, font=fnt, fill=color)
    return width


def stat_value(draw, data: SkillData, label: str, value: str, x: int, y: int, width: int, *, value_color):
    size = 13
    lab = font_w(size, WEIGHT_SEMI, data.locale)
    label_w = draw.textlength(label, font=lab)
    while size > 9 and draw.textlength(value, font=font_w(size, WEIGHT_REGULAR, data.locale)) > width - label_w - 16:
        size -= 1
    fnt = font_w(size, WEIGHT_REGULAR, data.locale)
    draw.text((x, y), label, font=lab, fill=MUTED)
    value_w = draw.textlength(value, font=fnt)
    draw.text((x + width - value_w, y), value, font=fnt, fill=value_color)
    draw.line((x, y + STATS_ROW - 4, x + width, y + STATS_ROW - 4), fill=(255, 255, 255, 16), width=1)


def stats_block(canvas, draw, data: SkillData, group: SkillGroup, x: int, y: int, width: int) -> int:
    composite_panel(
        canvas,
        (x, y, x + width, y + STATS_H),
        10,
        (16, 12, 27, 226),
        (255, 255, 255, 22),
    )
    inner_x = x + 12
    inner_w = width - 24
    rows = (
        (ui(data, "energy"), group.energy),
        (ui(data, "toughness"), group.toughness),
        (ui(data, "sp"), group.sp_change),
    )
    for index, (label, value) in enumerate(rows):
        stat_value(
            draw, data, label, value,
            inner_x, y + 6 + index * STATS_ROW, inner_w,
            value_color=MUTED if value == DASH else VALUE,
        )
    return y + STATS_H


def measure_glossary(draw, data: SkillData, term: GlossaryTerm, width: int) -> int:
    body_w = width - GLOSSARY_INNER * 2
    lines = layout_lines(draw, glossary_tokens(term), body_w, GLOSSARY_BODY_SIZE, data.locale)
    return 22 + len(lines) * GLOSSARY_LINE + 8


def glossary_block(canvas, draw, data: SkillData, term: GlossaryTerm, x: int, y: int, width: int) -> int:
    height = measure_glossary(draw, data, term, width)
    composite_panel(
        canvas,
        (x, y, x + width, y + height),
        9,
        (30, 24, 47, 238),
        (255, 255, 255, 26),
    )
    draw.text(
        (x + GLOSSARY_INNER, y + 7),
        term.name,
        font=font_w(GLOSSARY_TITLE_SIZE, WEIGHT_SEMI, data.locale),
        fill=TEXT,
    )
    lines = layout_lines(draw, glossary_tokens(term), width - GLOSSARY_INNER * 2, GLOSSARY_BODY_SIZE, data.locale)
    draw_lines(
        draw, lines, x + GLOSSARY_INNER, y + 22,
        GLOSSARY_BODY_SIZE, GLOSSARY_LINE, data.locale,
    )
    return y + height


def measure_skill_panel(draw, data: SkillData, panel: SkillPanel, width: int, body_size: int) -> int:
    group = panel.group
    natural = skill_header(draw, data, group, 0, 0, width)
    body_size_h = body_size + 5
    if panel.lines is not None:
        lines = panel.lines
    else:
        tokens = description_tokens(group)
        lines = trim_blank_lines(layout_lines(draw, tokens, skill_text_width(width), body_size, data.locale))
    natural += len(lines) * body_size_h + SKILL_BOTTOM + 4
    if panel.parts > 1:
        natural += 18
    if panel.extras and group.extras:
        natural += 12
        natural += sum(GLOSSARY_GAP + measure_glossary(draw, data, term, skill_text_width(width)) for term in group.extras)
    if panel.stats:
        natural += STATS_GAP + STATS_H
    return natural


def measure_skill_card(draw, data: SkillData, panel: SkillPanel, width: int, body_size: int) -> int:
    return measure_skill_panel(draw, data, panel, width, body_size)


def measure_eidolon_card(draw, data: SkillData, rank: RankRow, width: int, body_size: int, extras: bool = True) -> int:
    natural = 54
    runs = rank.diff_runs if rank.diff_runs is not None else eidolon_tokens(rank)
    natural += measure_runs(draw, runs, width - EID_PAD * 2, body_size, body_size + 4, data.locale)[0]
    natural += EID_BOTTOM
    if extras and rank.extras:
        natural += 10
        natural += sum(GLOSSARY_GAP + measure_glossary(draw, data, term, width - EID_PAD * 2) for term in rank.extras)
    return natural


def change_overlay(canvas, box, *, radius: int = 18) -> None:
    """Tint a changed comparison block without obscuring its contents."""
    x0, y0, x1, y1 = (round(value) for value in box)
    layer = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(
        (0, 0, layer.width - 1, layer.height - 1),
        radius=radius,
        fill=(142, 216, 168, 22),
        outline=(142, 216, 168, 52),
        width=1,
    )
    canvas.alpha_composite(layer, (x0, y0))


def change_badge(draw, x: int, y: int, text: str = "CHANGED", locale: str = "en") -> None:
    fnt = font_w(9, WEIGHT_SEMI, locale)
    width = draw.textlength(text, font=fnt) + 14
    draw.rounded_rectangle(
        (x, y, x + width, y + 16),
        radius=8,
        fill=(142, 216, 168, 24),
        outline=(142, 216, 168, 68),
        width=1,
    )
    draw.text((x + 7, y + 3), text, font=fnt, fill=(142, 216, 168, 255))

def skill_card(
    canvas,
    draw,
    data: SkillData,
    panel: SkillPanel,
    x: int,
    y: int,
    width: int,
    height: int,
    body_size: int,
    max_lines: int | None = None,
):
    group = panel.group
    natural = measure_skill_panel(draw, data, panel, width, body_size)
    composite_panel(canvas, (x, y, x + width, y + height), 18, CARD_FILL, CARD_EDGE)
    icon = skill_icon(data, group, 52)
    if icon:
        canvas.alpha_composite(icon, (x + 15, y + 13))
    else:
        draw.ellipse((x + 15, y + 13, x + 67, y + 65), fill=(190, 151, 255, 24), outline=(190, 151, 255, 80), width=1)
        draw.text((x + 29, y + 30), group.type_label[:3], font=font(11, bold=True), fill=PURPLE)
    text_x = x + 80
    header_label = f"{group.type_label}  /  PART {panel.part} OF {panel.parts}" if panel.parts > 1 else group.type_label
    draw.text((text_x, y + 9), header_label, font=font_w(10, WEIGHT_SEMI, data.locale), fill=PURPLE)

    title_y = y + 27
    for line in skill_title_lines(draw, data, group, width):
        title_runs(draw, line, SKILL_TITLE_SIZE, data, text_x, title_y)
        title_y += SKILL_TITLE_STEP
    level_text = f"Lv. {group.cap}" if group.level_rows and group.cap > 0 else ui(data, "passive")
    level_font = font_w(10, WEIGHT_SEMI, data.locale)
    level_w = draw.textlength(level_text, font=level_font)
    composite_panel(
        canvas,
        (x + width - level_w - 30, y + 9, x + width - 14, y + 31),
        11,
        (244, 201, 107, 18),
        (244, 201, 107, 80),
    )
    draw.text((x + width - level_w - 22, y + 14), level_text, font=level_font, fill=GOLD)


    body_y = skill_header(draw, data, group, x, y, width) + 4
    draw.line((x + 16, body_y - 16, x + width - 16, body_y - 16), fill=LINE, width=1)
    if panel.lines is not None:
        lines = panel.lines
    else:
        tokens = description_tokens(group)
        lines = trim_blank_lines(layout_lines(draw, tokens, skill_text_width(width), body_size, data.locale))
    if max_lines is not None:
        lines = lines[:max_lines]
    draw_lines(
        draw, lines, x + SKILL_PAD, body_y,
        body_size, body_size + 5, data.locale,
    )
    body_y += len(lines) * (body_size + 5)

    if panel.parts > 1:
        body_y += 10

    if panel.extras and group.extras:
        body_y += 6
        inner_w = skill_text_width(width)
        for term in group.extras:
            body_y = glossary_block(canvas, draw, data, term, x + SKILL_PAD, body_y, inner_w) + GLOSSARY_GAP
        body_y -= GLOSSARY_GAP
        body_y += 6

    if panel.stats:
        stats_y = body_y + STATS_GAP
        stats_block(canvas, draw, data, group, x + SKILL_PAD, stats_y, skill_text_width(width))
    if group.change is not None:
        change_overlay(canvas, (x, y, x + width, y + height), radius=18)
        change_badge(draw, x + width - 84, y + 35, locale=data.locale)


def eidolon_card(
    canvas,
    draw,
    data: SkillData,
    rank: RankRow,
    x: int,
    y: int,
    width: int,
    height: int,
    body_size: int,
    max_lines: int | None = None,
    extras: bool = True,
):
    natural = measure_eidolon_card(draw, data, rank, width, body_size)
    composite_panel(canvas, (x, y, x + width, y + height), 16, CARD_FILL, CARD_EDGE)
    icon = previous_eidolon_icon(data, rank, 40)
    if icon:
        canvas.alpha_composite(icon, (x + 14, y + 11))
    else:
        draw.ellipse((x + 14, y + 11, x + 54, y + 51), fill=(190, 151, 255, 28), outline=(190, 151, 255, 95), width=1)
        draw.text((x + 20, y + 22), "PREV", font=font(9, bold=True), fill=PURPLE)
    text_x = x + 64
    draw.text((text_x, y + 8), f"E{rank.key}", font=font_w(10, WEIGHT_SEMI, data.locale), fill=PURPLE)
    title_width = width - 78 - 48
    title = fit(draw, rank.name, font(EID_TITLE_SIZE, bold=True, locale=data.locale), title_width)
    title_runs(draw, title, EID_TITLE_SIZE, data, text_x, y + 24)
    current = eidolon_icon(data, rank, 40)
    if current:
        canvas.alpha_composite(current, (x + width - 54, y + 11))
    else:
        draw.ellipse((x + width - 54, y + 11, x + width - 14, y + 51), fill=(190, 151, 255, 22), outline=(190, 151, 255, 80), width=1)
        draw.text((x + width - 46, y + 26), str(rank.key), font=font(11, bold=True), fill=PURPLE)
    draw.line((x + 14, y + 50, x + width - 14, y + 50), fill=LINE, width=1)
    body_y = y + 54
    runs = rank.diff_runs if rank.diff_runs is not None else eidolon_tokens(rank)
    body_y += draw_lines(
        draw,
        layout_lines(draw, runs, width - EID_PAD * 2, body_size, data.locale),
        x + EID_PAD,
        body_y,
        body_size,
        body_size + 4,
        data.locale,
        max_lines=max_lines,
    )
    if extras and rank.extras and max_lines is None:
        body_y += 10
        inner_w = width - EID_PAD * 2
        for term in rank.extras:
            body_y = glossary_block(canvas, draw, data, term, x + EID_PAD, body_y, inner_w) + GLOSSARY_GAP
        body_y -= GLOSSARY_GAP
    if rank.change is not None:
        change_overlay(canvas, (x, y, x + width, y + height), radius=16)
        change_badge(draw, x + width - 84, y + 35, locale=data.locale)



def footer_version(data: SkillData) -> str:
    if data.comparison:
        return f"v{data.version_before} \u2192 v{data.version_after}"
    return f"v{data.version}"


def draw_footer(draw, width: int, height: int, data: SkillData, page: str):
    draw.line((M, height - 42, width - M, height - 42), fill=LINE, width=1)
    draw.text(
        (M, height - 29),
        f"NANOKA HSR  /  DATA {footer_version(data)}  /  {data.locale.upper()}",
        font=font_w(10, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
    page_w = draw.textlength(page, font=font_w(10, WEIGHT_SEMI, data.locale))
    draw.text(
        (width - M - page_w, height - 29),
        page,
        font=font_w(10, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )

def skill_sections(data: SkillData) -> list[tuple[str, list[SkillGroup], str]]:
    combat = [group for group in data.skills if group.scope == "character"]
    memo = [group for group in data.skills if group.scope == "memosprite"]
    sections: list[tuple[str, list[SkillGroup], str]] = []
    if combat:
        sections.append((ui(data, "skills"), combat, f"{len(combat)} SKILLS"))
    if memo:
        subtitle = f"{data.memosprite_name.upper()}  /  {len(memo)} SKILLS" if data.memosprite_name else f"{len(memo)} SKILLS"
        sections.append((ui(data, "memosprite"), memo, subtitle))
    return sections


def closest_cut(cuts: list[int], value: int) -> int:
    return min(abs(value - cut) for cut in cuts)


def sentence_cuts(raw: str, spaces: list[int]) -> list[int]:
    """Prefer places right after sentence punctuation (outside markup)."""
    result = []
    for index in spaces:
        prefix = raw[:index].rstrip()
        if prefix and prefix[-1] in ".!?":
            result.append(index)
    return result


def safe_cuts(raw: str) -> list[int]:
    """Space offsets that never fall inside Nanoka markup."""
    result = []
    depth = 0
    for index, char in enumerate(raw):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif char == " " and depth == 0 and index > 0:
            result.append(index)
    return result


def _chunk_lines(lines: list[list[Piece]], parts: int) -> list[list[list[Piece]]]:
    """Split laid-out lines into balanced chunks, preferring sentence ends."""
    if parts <= 1 or len(lines) <= 1:
        return [lines]
    total = len(lines)
    step = total / parts
    boundaries = [0]
    for part in range(1, parts):
        target = round(step * part)
        window = max(2, round(step * 0.35))
        best = None
        for candidate in range(max(1, target - window), min(total, target + window + 1)):
            score = abs(candidate - target)
            previous = "".join(piece.text for piece in lines[candidate - 1]).strip()
            if previous.endswith((".", "!", "?")):
                score -= step * 0.6
            if best is None or score < best[0]:
                best = (score, candidate)
        boundary = best[1] if best else target
        if boundary > boundaries[-1]:
            boundaries.append(boundary)
    boundaries.append(total)
    return [lines[boundaries[index]:boundaries[index + 1]] for index in range(len(boundaries) - 1)]


def split_group(data: SkillData, draw, group: SkillGroup, width: int, body_size: int) -> list[SkillPanel]:
    """Split very long descriptions into readable, balanced cards.

    Splitting happens on the laid-out line list, so every part is rendered
    from the exact same rich-text pieces as the unsplit card. Parts after the
    first start with a continuation marker and only the final part carries
    the glossary and stats block.
    """
    raw = normalize_breaks(group.raw_desc or group.desc or "")
    tokens = desc_tokens(raw, {row.index: row for row in group.rows}, VALUE, group_columns(group))
    lines = trim_blank_lines(layout_lines(draw, tokens, skill_text_width(width), body_size, data.locale))
    line_h = body_size + 5
    total_h = len(lines) * line_h
    if total_h <= DESC_SPLIT_H:
        return [SkillPanel(group=group, desc=raw, part=1, parts=1)]

    glossary_h = 12 + sum(
        GLOSSARY_GAP + measure_glossary(draw, data, term, skill_text_width(width))
        for term in group.extras
    ) if group.extras else 0
    stats_h = STATS_GAP + STATS_H
    body_start = skill_header(draw, data, group, 0, 0, width)
    card_cap = DESC_TARGET_H + body_start + glossary_h + stats_h + 40
    total_card_h = body_start + total_h + glossary_h + stats_h
    parts = min(MAX_PARTS, max(2, math.ceil(total_card_h / card_cap)))

    chunks = _chunk_lines(lines, parts)
    if len(chunks) < 2:
        return [SkillPanel(group=group, desc=raw, part=1, parts=1)]

    panels = []
    for index, chunk in enumerate(chunks):
        chunk = list(chunk)
        if index > 0 and chunk:
            first = chunk[0]
            marker = Piece("\u2026 ", BODY_SOFT, WEIGHT_REGULAR)
            chunk[0] = [marker] + first
        panels.append(
            SkillPanel(
                group=group,
                desc=raw,
                part=index + 1,
                parts=len(chunks),
                extras=index == len(chunks) - 1,
                stats=index == len(chunks) - 1,
                lines=chunk,
            )
        )
    return panels


def masonry_columns(heights: list[int], cols: int, gap: int) -> list[float]:
    """Assign cards to the shortest column; keeps reading order per column."""
    sums = [0.0] * cols
    for height in heights:
        index = sums.index(min(sums))
        sums[index] += height + gap
    return sums


def slot_groups(panels: list[SkillPanel], heights: list[int]) -> list[list[int]]:
    """Group split parts so "Part 1/2" and "Part 2/2" stay together.

    A group occupies one masonry slot and its panels render one after another
    inside that slot; parts never land in different columns.
    """
    groups: list[list[int]] = []
    for index, panel in enumerate(panels):
        if panel.part > 1 and groups:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def section_layout(data: SkillData, draw, groups: list[SkillGroup], body_size: int, cols: int, left_w: int) -> dict:
    width = (left_w - GAP * (cols - 1)) // cols
    panels: list[SkillPanel] = []
    base_heights = []
    for group in groups:
        group_panels = split_group(data, draw, group, width, body_size)
        base_heights.append(measure_skill_card(draw, data, group_panels[0], width, body_size))
        panels.extend(group_panels)
    heights = [measure_skill_card(draw, data, panel, width, body_size) for panel in panels]
    groups_index = slot_groups(panels, heights)
    group_heights = [
        sum(heights[index] for index in indices) + ROW_GAP * max(0, len(indices) - 1)
        for indices in groups_index
    ]
    sums = masonry_columns(group_heights, cols, ROW_GAP)
    column_heights = [0.0] * cols
    for indices, height in zip(groups_index, group_heights):
        slot = column_heights.index(min(column_heights))
        column_heights[slot] += height + ROW_GAP
    total = math.ceil(max(column_heights)) if column_heights else 0
    imbalance = (max(column_heights) - min(column_heights)) / (max(column_heights) or 1) if column_heights else 0.0
    cards = len(panels) or 1
    orphan = 0.05 if cards < cols else 0.0
    short_cards = sum(1 for height in base_heights if height < 260)
    short_penalty = short_cards * 0.04
    cost = total * (1.0 + imbalance * 0.45 + orphan + short_penalty)
    return {
        "cols": cols, "width": width, "panels": panels, "heights": heights,
        "groups": groups_index, "group_heights": group_heights,
        "columns": column_heights, "total": total, "cost": cost,
    }


def best_section_layout(data: SkillData, draw, groups: list[SkillGroup], body_size: int, left_w: int) -> dict:
    return section_layout(data, draw, groups, body_size, 2, left_w)


def is_large_frame(data: SkillData, height: int) -> bool:
    return height > 1900


def body_sizes(data: SkillData, height: int) -> tuple[int, ...]:
    if is_large_frame(data, height):
        return (19, 18, 17, 16, 15, 14, 13)
    return (18, 17, 16, 15, 14, 13)

def eidolon_heights(data: SkillData, draw, body_size: int, width: int = RIGHT_W) -> list[int]:
    return [measure_eidolon_card(draw, data, rank, width, body_size) for rank in data.eidolons]


def distribute_even(item_heights: list[int], gap: int, available: int) -> tuple[list[int], int]:
    """Keep cards at their natural heights; unused space stays below the stack."""
    return list(item_heights), gap
MAX_PAGE_H = 6400


def plan_page(data: SkillData, draw) -> dict:
    """Pick font sizes and section layout, growing the canvas for long kits."""
    sections = skill_sections(data)
    chosen = None
    sizes = body_sizes(data, H)
    for body_size in sizes:
        layouts = [best_section_layout(data, draw, groups, body_size, LEFT_W) for _, groups, _ in sections]
        left_total = sum(layout["total"] for layout in layouts) + SECTION_GAP * max(0, len(layouts) - 1)
        left_total += SECTION_HEAD_H * len(layouts)
        eid_size = max(13, body_size - 2)
        eid_heights = eidolon_heights(data, draw, eid_size)
        eid_total = sum(eid_heights) + EID_GAP * max(0, len(eid_heights) - 1)
        height = max(H, CONTENT_TOP + max(left_total, eid_total) + BOTTOM_RESERVE + 10)
        if height > MAX_PAGE_H:
            continue
        chosen = {
            "body": body_size, "eid": eid_size, "height": height,
            "sections": sections, "layouts": layouts, "eid_heights": eid_heights,
        }
        break

    if chosen is None:
        body_size = 13
        layouts = [best_section_layout(data, draw, groups, body_size, LEFT_W) for _, groups, _ in sections]
        left_total = sum(layout["total"] for layout in layouts) + SECTION_GAP * max(0, len(layouts) - 1)
        left_total += SECTION_HEAD_H * len(layouts)
        eid_size = 13
        eid_heights = eidolon_heights(data, draw, eid_size)
        eid_total = sum(eid_heights) + EID_GAP * max(0, len(eid_heights) - 1)
        height = max(H, CONTENT_TOP + max(left_total, eid_total) + BOTTOM_RESERVE + 10)
        chosen = {
            "body": body_size, "eid": eid_size, "height": height,
            "sections": sections, "layouts": layouts, "eid_heights": eid_heights,
        }
    return chosen


def render_full(data: SkillData) -> SkillsCardResult:
    scratch = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(scratch)
    plan = plan_page(data, draw)
    height = plan["height"]
    body_size = plan["body"]
    eid_size = plan["eid"]
    available = height - CONTENT_TOP - BOTTOM_RESERVE

    eid_heights, eid_gap = distribute_even(plan["eid_heights"], EID_GAP, available)

    canvas = page_background(W, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, W, HEADER_H)
    section_title(draw, RIGHT_X, SECTION_TOP, ui(data, "eidolons"), ui(data, "eidolons_sub"), RIGHT_W, data.locale)

    y = CONTENT_TOP
    for (title, groups, subtitle), layout in zip(plan["sections"], plan["layouts"]):
        section_title(draw, M, y, title, subtitle, LEFT_W, data.locale)
        y += SECTION_HEAD_H
        cols = [0.0] * layout["cols"]
        for indices, group_h in zip(layout["groups"], layout["group_heights"]):
            slot = cols.index(min(cols))
            x = M + slot * (layout["width"] + GAP)
            panel_y = y + cols[slot]
            for index in indices:
                panel = layout["panels"][index]
                panel_h = layout["heights"][index]
                skill_card(canvas, draw, data, panel, x, round(panel_y), layout["width"], panel_h, body_size)
                panel_y += panel_h + ROW_GAP
            cols[slot] += group_h + ROW_GAP
        y += max(cols) + SECTION_GAP

    y = CONTENT_TOP
    for rank, eid_h in zip(data.eidolons, eid_heights):
        eidolon_card(canvas, draw, data, rank, RIGHT_X, y, RIGHT_W, eid_h, eid_size)
        y += eid_h + eid_gap

    draw_footer(draw, W, height, data, ui(data, "footer"))
    tables, dropdowns = build_tables(data)
    return SkillsCardResult(
        image=canvas,
        tables=tables,
        dropdowns=dropdowns,
        sections=build_sections(data),
    )

def render_summary(data: SkillData) -> Image.Image:
    width = W
    col_w = (LEFT_W - GAP) // 2
    body_size = 15
    eid_body = 14
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    skills = data.skills[:6]
    panels = [SkillPanel(group=group, desc=group.raw_desc or group.desc, extras=False, stats=False) for group in skills]
    row_need = []
    for index in range(0, len(panels), 2):
        heights = [
            measure_skill_card(probe, data, panel, col_w, body_size)
            for panel in panels[index:index + 2]
        ]
        row_need.append(max(heights, default=160))
    eid_need = [measure_eidolon_card(probe, data, rank, RIGHT_W, eid_body, extras=False) for rank in data.eidolons]
    left_h = sum(row_need) + ROW_GAP * max(0, len(row_need) - 1)
    right_h = sum(eid_need) + EID_GAP * max(0, len(eid_need) - 1)
    height = max(1080, CONTENT_TOP + max(left_h, right_h) + BOTTOM_RESERVE)
    canvas = page_background(width, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, width, HEADER_H)
    section_title(draw, M, SECTION_TOP, ui(data, "skills"), ui(data, "skills_sub"), LEFT_W, data.locale)
    section_title(draw, RIGHT_X, SECTION_TOP, ui(data, "eidolons"), ui(data, "eidolons_sub"), RIGHT_W, data.locale)
    y = CONTENT_TOP
    for row, row_h in enumerate(row_need):
        for col in range(2):
            index = row * 2 + col
            if index >= len(panels):
                continue
            x = M + col * (col_w + GAP)
            skill_card(canvas, draw, data, panels[index], x, y, col_w, row_h, body_size=body_size)
        y += row_h + ROW_GAP
    y = CONTENT_TOP
    for rank, eid_h in zip(data.eidolons, eid_need):
        eidolon_card(canvas, draw, data, rank, RIGHT_X, y, RIGHT_W, eid_h, body_size=eid_body, extras=False)
        y += eid_h + EID_GAP
    draw_footer(draw, width, height, data, ui(data, "footer"))
    return canvas


def render_skill_page(data: SkillData, skills: list[SkillGroup], page_number: int, page_count: int) -> Image.Image:
    width = 1920
    col_w = (W - M * 2 - GAP) // 2
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    panels = [
        SkillPanel(group=group, desc=group.raw_desc or group.desc, extras=True, stats=True)
        for group in skills
    ]
    heights = [measure_skill_card(probe, data, panel, col_w, 16) for panel in panels]
    row_heights = [max(heights[i:i + 2]) for i in range(0, len(heights), 2)]
    height = max(1440, CONTENT_TOP + sum(row_heights) + ROW_GAP * max(0, len(row_heights) - 1) + BOTTOM_RESERVE + 10)
    canvas = page_background(width, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, width, HEADER_H)
    section_title(draw, M, SECTION_TOP, ui(data, "skills"), f"{page_number} / {page_count}", W - M * 2, data.locale)
    y = CONTENT_TOP
    for row, row_h in enumerate(row_heights):
        for col in range(2):
            index = row * 2 + col
            if index >= len(panels):
                continue
            x = M + col * (col_w + GAP)
            skill_card(canvas, draw, data, panels[index], x, y, col_w, row_h, body_size=16)
        y += row_h + ROW_GAP
    draw_footer(draw, width, height, data, ui(data, "footer"))
    return canvas


def render_eidolon_page(data: SkillData) -> Image.Image:
    width = 1920
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    col_w = (width - M * 2 - GAP) // 2
    need = [measure_eidolon_card(probe, data, rank, col_w, 15) for rank in data.eidolons[:6]]
    row_need = [max(need[i:i + 2]) for i in range(0, len(need), 2)]
    height = max(1080, CONTENT_TOP + sum(row_need) + 12 * max(0, len(row_need) - 1) + BOTTOM_RESERVE)
    canvas = page_background(width, height)
    draw = ImageDraw.Draw(canvas)
    header(canvas, draw, data, width, HEADER_H)
    section_title(draw, M, SECTION_TOP, ui(data, "eidolons"), "E1 - E6", W - M * 2, data.locale)
    card_h = 220
    col_w = (W - M * 2 - GAP) // 2
    ranks = data.eidolons[:6]
    rows = max(1, math.ceil(len(ranks) / 2))
    row_space = (height - CONTENT_TOP - BOTTOM_RESERVE - 12 * max(0, rows - 1)) // rows
    heights = [measure_eidolon_card(draw, data, rank, col_w, 15) for rank in ranks]
    row_heights = [max(heights[i:i + 2]) for i in range(0, len(heights), 2)]
    y = CONTENT_TOP
    for row, row_h in enumerate(row_heights):
        for col in range(2):
            index = row * 2 + col
            if index >= len(ranks):
                continue
            x = M + col * (col_w + GAP)
            eidolon_card(canvas, draw, data, ranks[index], x, y, col_w, row_h, body_size=15)
        y += row_h + 12
    draw_footer(draw, width, height, data, ui(data, "footer"))
    return canvas


async def load_data(
    character_id: int | str,
    locale: str,
    *,
    version: str | None = None,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[SkillData, CharacterData]:
    """Build the renderer model from the shared version-aware loader."""
    character = await load_character(
        character_id,
        version=version,
        locale=locale,
        cache_dir=cache_dir,
        proxy=proxy,
    )
    try:
        return await build_skill_data(character), character
    except BaseException:
        await character.client.close()
        raise


async def build_skill_data(character: CharacterData) -> SkillData:
    detail = character.detail
    locale = character.locale
    character_id = character.character_id
    record = character.catalog_record
    description = plain(character.description)
    element = character.element
    path = character.path
    element_labels = ELEMENT_LABELS.get(locale, ELEMENT_LABELS["en"])
    path_labels = PATH_LABELS.get(locale, PATH_LABELS["en"])
    memosprite = detail.memosprite or {}
    spprite_name = clean_localized(str(memosprite.get("name") or ""), locale) or ""
    spprite_icon = Path(str(memosprite.get("icon") or "")).stem
    spprite_code = "".join(ch for ch in spprite_icon if ch.isdigit())

    relatives = [
        f"avatardrawcard/{character_id}.webp",
        f"element/{element}.webp",
        f"pathicon/{path}.webp",
    ]
    for icon in (
        "IconMaxHP",
        "IconAttack",
        "IconDefence",
        "IconSpeed",
        "IconCriticalChance",
        "IconCriticalDamage",
        "IconFireAddedRatio",
        "IconIceAddedRatio",
        "IconWindAddedRatio",
        "IconThunderAddedRatio",
        "IconPhysicalAddedRatio",
        "IconQuantumAddedRatio",
        "IconImaginaryAddedRatio",
    ):
        relatives.append(f"skillicons/{icon}.webp")
    for suffix in ("Normal", "BP", "Ultra", "Passive", "Maze"):
        relatives.append(f"skillicons/SkillIcon_{character_id}_{suffix}.webp")
    if spprite_code:
        relatives.extend(
            [
                f"skillicons/SkillIcon_{spprite_code}_Servant.webp",
                f"skillicons/SkillIcon_{spprite_code}_ServantPassive.webp",
            ]
        )
    ranks = rank_rows(detail.ranks)
    for rank in ranks:
        icon = rank_icon_relative(rank.rank.icon)
        if icon:
            relatives.append(icon)
    await prime_assets(character, relatives)

    rank_dir = None
    if ranks:
        first_rank = await character.asset(rank_texture_relative(character_id, ranks[0].key))
        for rank in ranks:
            await character.asset(rank_texture_relative(character_id, rank.key))
        if first_rank is not None:
            rank_dir = first_rank.parent

    data = SkillData(
        character_id=character_id,
        locale=locale,
        version=character.version,
        name=clean_localized(character.name, locale) or str(character_id),
        description=description,
        element_label=element_labels.get(element, element.title()),
        path_label=path_labels.get(path, (detail.path or "").title()),
        stars=character.stars,
        splash=load_webp(character.client.cache.asset_file(f"avatardrawcard/{character_id}.webp")),
        element_icon=load_webp(character.client.cache.asset_file(f"element/{element}.webp")),
        path_icon=load_webp(character.client.cache.asset_file(f"pathicon/{path}.webp")),
        skill_icon_dir=character.client.cache.asset_file("skillicons"),
        rank_icon_dir=rank_dir,
        skills=skill_groups(detail),
        eidolons=ranks,
        memosprite_name=spprite_name,
        memosprite_code=spprite_code,
        detail=detail,
        stats=max_stats(detail),
        bonuses=bonus_stats(detail, locale),
        sp_need=detail.sp_need or 0,
        items=character.items,
    )
    return data


async def build_comparison_data(
    character_id: int | str,
    from_version: str,
    to_version: str,
    locale: str = "en",
    *,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> tuple[SkillData, CharacterData, CharacterData]:
    """Build a skills card model that marks every changed skill/eidolon."""
    before_data = await load_character(
        character_id, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy
    )
    try:
        after_data = await load_character(
            character_id, version=to_version, locale=locale, cache_dir=cache_dir, proxy=proxy
        )
    except BaseException:
        await before_data.client.close()
        raise
    try:
        before = await build_skill_data(before_data)
        after = await build_skill_data(after_data)
    except BaseException:
        await before_data.client.close()
        await after_data.client.close()
        raise
    mark_skill_diff(before, after)
    after.version_before = before.version
    after.version_after = after.version
    after.stats_before = before.stats
    after.bonuses_before = before.bonuses
    after.sp_need_before = before.sp_need
    return after, before_data, after_data


def mark_skill_diff(before: SkillData, after: SkillData) -> None:
    """Attach inline word diffs to the ``after`` model."""
    previous_skills = {group.key: group for group in before.skills}
    for group in after.skills:
        old = previous_skills.get(group.key)
        if old is None:
            group.change = "new"
            group.diff_runs = _runs_with_added(
                description_tokens(group), KIND_COLOR["added"]
            )
            continue
        old_runs = description_tokens(old)
        new_runs = description_tokens(group)
        if _plain_runs(old_runs) == _plain_runs(new_runs):
            group.change = None
            continue
        group.before = old
        group.change = "changed"
        group.diff_runs = diff_runs(old_runs, new_runs, locale=group_locale(after))

    previous_ranks = {rank.key: rank for rank in before.eidolons}
    for rank in after.eidolons:
        old = previous_ranks.get(rank.key)
        if old is None:
            rank.change = "new"
            rank.diff_runs = _runs_with_added(eidolon_tokens(rank), KIND_COLOR["added"])
            continue
        old_runs = eidolon_tokens(old)
        new_runs = eidolon_tokens(rank)
        if _plain_runs(old_runs) == _plain_runs(new_runs):
            rank.change = None
            continue
        rank.before = old
        rank.change = "changed"
        rank.diff_runs = diff_runs(old_runs, new_runs, locale=group_locale(after))


def group_locale(data: SkillData) -> str:
    return data.locale


def _plain_runs(runs) -> str:
    return " ".join(text for text, kind, _ in runs if text != "\n" and text.strip())


def _runs_with_added(runs, color):
    return [
        (text, "added" if not kind.startswith("removed") else kind, color)
        if text != "\n"
        else (text, kind, color)
        for text, kind, color in runs
    ]


async def build_skills_card(
    character_id: int | str,
    locale: str = "en",
    *,
    version: str | None = None,
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
) -> SkillsCardResult:
    data, character = await load_data(
        character_id, locale, version=version, cache_dir=cache_dir, proxy=proxy
    )
    try:
        return render_full(data)
    finally:
        await character.client.close()


async def build(character_id: int, locale: str, variant: str, output: Path, json_output: bool = False):
    data, character = await load_data(character_id, locale)
    client = character.client
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = "" if locale == "en" else f"_{locale}"
    outputs = []
    if variant == "full":
        result = render_full(data)
        outputs.append((output.with_name(f"character_{character_id}_skills_full{suffix}.png"), result.image))
        if json_output:
            json_path = output.with_name(f"character_{character_id}_skills_tables{suffix}.json")
            json_path.write_text(
                json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"{json_path} | {len(result.tables)} tables | {len(result.dropdowns)} dropdowns")
    elif variant == "summary":
        outputs.append((output.with_name(f"character_{character_id}_skills_summary{suffix}.png"), render_summary(data)))
    else:
        pages = [data.skills[index:index + 6] for index in range(0, len(data.skills), 6)]
        for index, skills in enumerate(pages, start=1):
            outputs.append(
                (
                    output.with_name(f"character_{character_id}_skills_pages_{index}{suffix}.png"),
                    render_skill_page(data, skills, index, len(pages) + 1),
                )
            )
        outputs.append(
            (output.with_name(f"character_{character_id}_eidolons_pages{suffix}.png"), render_eidolon_page(data))
        )
    for path, image in outputs:
        image.convert("RGB").save(path, quality=94, subsampling=0)
        print(f"{path} | {image.width}x{image.height} | {path.stat().st_size:,} bytes")
    print(f"skills={len(data.skills)} | eidolons={len(data.eidolons)}")
    await client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("character_id", type=int)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--variant", choices=("full", "summary", "pages"), default="full")
    parser.add_argument("--out", type=Path, default=Path("out") / "skills.png")
    parser.add_argument("--json", action="store_true", help="Write the tables/dropdowns payload alongside the card")
    args = parser.parse_args()
    asyncio.run(build(args.character_id, args.locale, args.variant, args.out, args.json))


if __name__ == "__main__":
    main()
