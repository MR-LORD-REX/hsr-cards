"""Skills sheet dimensions, localized labels, text patterns, and palette."""
from __future__ import annotations

from PIL import ImageFont
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import TEXT
from pathlib import Path
from hsr_cards.utils.hsrfonts import WINDOWS_FONT_DIR
import re


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


WEIGHT_REGULAR = "regular"


WEIGHT_SEMI = "semi"


WEIGHT_BOLD = "bold"


FONT_DIR = WINDOWS_FONT_DIR


FONT_SEMI_FILE = FONT_DIR / "seguisb.ttf"


FONT_SYMBOLS = FONT_DIR / "seguisym.ttf"


FALLBACK_CHARS = set("\u266a\u2605\u221e\u25e6\u2606\u25a0\u2588")


_font_cache: dict[tuple[int, str, str], ImageFont.FreeTypeFont] = {}


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


MAX_PAGE_H = 6400
