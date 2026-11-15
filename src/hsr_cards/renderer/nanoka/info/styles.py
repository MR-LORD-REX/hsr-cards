"""Character info dimensions, palette, localized labels, and punctuation."""
from __future__ import annotations

import re


M = 48


CONTENT_W = 1080 - M * 2


CARD_FILL = (23, 18, 36, 235)


CARD_EDGE = (255, 255, 255, 34)


SOFT_EDGE = (255, 255, 255, 18)


ELEMENT_LABELS = {
    "en": {"fire": "Fire", "ice": "Ice", "wind": "Wind", "thunder": "Lightning", "physical": "Physical", "quantum": "Quantum", "imaginary": "Imaginary"},
    "zh": {"fire": "\u706b", "ice": "\u51b0", "wind": "\u98ce", "thunder": "\u96f7", "physical": "\u7269\u7406", "quantum": "\u91cf\u5b50", "imaginary": "\u865a\u6570"},
    "ja": {"fire": "\u708e", "ice": "\u6c37", "wind": "\u98a8", "thunder": "\u96f7", "physical": "\u7269\u7406", "quantum": "\u91cf\u5b50", "imaginary": "\u865a\u6570"},
    "ko": {"fire": "\ud654\uc5fc", "ice": "\uc5bc\uc74c", "wind": "\ubc14\ub78c", "thunder": "\ubc88\uac1c", "physical": "\ubb3c\ub9ac", "quantum": "\uc591\uc790", "imaginary": "\ud5c8\uc218"},
}


PATH_LABELS = {
    "en": {"warlock": "Nihility", "knight": "Preservation", "rogue": "The Hunt", "mage": "Erudition", "shaman": "Abundance", "warrior": "Destruction", "memory": "Remembrance", "elation": "Elation"},
    "zh": {"warlock": "\u865a\u65e0", "knight": "\u5b58\u62a4", "rogue": "\u5de1\u730e", "mage": "\u667a\u8bc6", "shaman": "\u4e30\u9976", "warrior": "\u6bc1\u706d", "memory": "\u8bb0\u5fc6", "elation": "\u6b22\u6109"},
    "ja": {"warlock": "\u865a\u7121", "knight": "\u5b58\u8b77", "rogue": "\u5de1\u72e9", "mage": "\u77e5\u6075", "shaman": "\u8c4a\u7a63", "warrior": "\u58ca\u6ec5", "memory": "\u8a18\u61b6", "elation": "\u6b53\u559c"},
    "ko": {"warlock": "\ud5c8\ubb34", "knight": "\ubcf4\uc874", "rogue": "\uc218\ub834", "mage": "\uc9c0\uc2dd", "shaman": "\ud48d\uc694", "warrior": "\ud30c\uba78", "memory": "\uae30\uc5b5", "elation": "\ud658\ub77d"},
}


UI_LABELS = {
    "en": {
        "character_card": "CHARACTER CARD", "materials": "MATERIALS",
        "base_stats": "BASE STATS", "stat_bonus": "STAT BONUS", "max_level": "MAX LEVEL 80",
        "hp": "HP", "atk": "ATK", "def": "DEF", "spd": "SPD", "crit_rate": "CRIT RATE", "crit_dmg": "CRIT DMG", "aggro": "AGGRO",
        "ascension": "ASCENSION MATERIALS", "level_range": "LV. 1 - 80",
        "skills": "SKILL MATERIALS", "all_skills": "ALL SKILLS TO LV. 10",
        "total_credits": "TOTAL CREDITS", "voice": "VOICE CAST",
        "base_stats": "BASE STATS", "max_level_short": "MAX LV. 80",
        "base_hp": "Base HP", "base_atk": "Base ATK", "base_def": "Base DEF", "base_spd": "Base SPD",
        "taunt": "Taunt", "max_energy": "Max Energy", "trace_stat_bonus": "TRACE STAT BONUS",
        "voice_cast": "VOICE CAST", "not_credited": "Not credited",
    },
    "zh": {
        "character_card": "\u89d2\u8272\u5361\u7247", "materials": "\u6750\u6599",
        "base_stats": "\u57fa\u7840\u5c5e\u6027", "stat_bonus": "\u5c5e\u6027\u52a0\u6210", "max_level": "\u6ee1\u7ea7 80",
        "hp": "\u751f\u547d\u503c", "atk": "\u653b\u51fb\u529b", "def": "\u9632\u5fa1\u529b", "spd": "\u901f\u5ea6", "crit_rate": "\u66b4\u51fb\u7387", "crit_dmg": "\u66b4\u51fb\u4f24\u5bb3", "aggro": "\u5632\u8bbd\u503c",
        "ascension": "\u664b\u9636\u6750\u6599", "level_range": "Lv. 1-80",
        "skills": "\u884c\u8ff9\u6750\u6599", "all_skills": "\u5168\u90e8\u884c\u8ff9 Lv.10",
        "total_credits": "\u4fe1\u7528\u70b9\u603b\u8ba1", "voice": "\u58f0\u4f18",
        "base_stats": "\u57fa\u7840\u5c5e\u6027", "max_level_short": "\u6ee1\u7ea7 80",
        "base_hp": "\u57fa\u7840\u751f\u547d\u503c", "base_atk": "\u57fa\u7840\u653b\u51fb\u529b", "base_def": "\u57fa\u7840\u9632\u5fa1\u529b", "base_spd": "\u57fa\u7840\u901f\u5ea6",
        "taunt": "\u5632\u8bbd\u503c", "max_energy": "\u6700\u5927\u80fd\u91cf", "trace_stat_bonus": "\u884c\u8ff9\u5c5e\u6027\u52a0\u6210",
        "voice_cast": "\u58f0\u4f18", "not_credited": "\u6682\u65e0\u8bb0\u5f55",
    },
    "ja": {
        "character_card": "\u30ad\u30e3\u30e9\u30af\u30bf\u30fc\u30ab\u30fc\u30c9", "materials": "\u7d20\u6750",
        "base_stats": "\u57fa\u672c\u30b9\u30c6\u30fc\u30bf\u30b9", "stat_bonus": "\u30b9\u30c6\u30fc\u30bf\u30b9\u30dc\u30fc\u30ca\u30b9", "max_level": "\u6700\u5927Lv.80",
        "hp": "HP", "atk": "\u653b\u6483\u529b", "def": "\u9632\u5fa1\u529b", "spd": "\u901f\u5ea6", "crit_rate": "\u4f1a\u5fc3\u7387", "crit_dmg": "\u4f1a\u5fc3\u30c0\u30e1\u30fc\u30b8", "aggro": "AGGRO",
        "ascension": "\u6607\u683c\u7d20\u6750", "level_range": "Lv. 1-80",
        "skills": "\u8ecc\u8de1\u7d20\u6750", "all_skills": "\u5168\u8ecc\u8de1 Lv.10",
        "total_credits": "\u5fc5\u8981\u30af\u30ec\u30b8\u30c3\u30c8", "voice": "\u58f0\u512a",
        "base_stats": "\u57fa\u672c\u30b9\u30c6\u30fc\u30bf\u30b9", "max_level_short": "\u6700\u5927Lv.80",
        "base_hp": "\u57fa\u790eHP", "base_atk": "\u57fa\u790e\u653b\u6483\u529b", "base_def": "\u57fa\u790e\u9632\u5fa1\u529b", "base_spd": "\u57fa\u790e\u901f\u5ea6",
        "taunt": "\u6311\u767a\u5024", "max_energy": "\u6700\u5927EP", "trace_stat_bonus": "\u8ecc\u8de1\u30dc\u30fc\u30ca\u30b9",
        "voice_cast": "\u58f0\u512a", "not_credited": "\u672a\u767b\u9332",
    },
    "ko": {
        "character_card": "\uce90\ub9ad\ud130 \uce74\ub4dc", "materials": "\uc7ac\ub8cc",
        "base_stats": "\uae30\ubcf8 \ub2a5\ub825\uce58", "stat_bonus": "\ub2a5\ub825\uce58 \ubcf4\ub108\uc2a4", "max_level": "\ucd5c\ub300 Lv.80",
        "hp": "HP", "atk": "\uacf5\uaca9\ub825", "def": "\ubc29\uc5b4\ub825", "spd": "\uc18d\ub3c4", "crit_rate": "\uce58\uba85\ud0c0 \ud655\ub960", "crit_dmg": "\uce58\uba85\ud0c0 \ud53c\ud574", "aggro": "AGGRO",
        "ascension": "\uc2b9\uae09 \uc7ac\ub8cc", "level_range": "Lv. 1-80",
        "skills": "\uada4\uc801 \uc7ac\ub8cc", "all_skills": "\ubaa8\ub4e0 \uc2a4\ud0ac Lv.10",
        "total_credits": "\ucd1d \ud06c\ub808\ub527", "voice": "\uc131\uc6b0",
        "base_stats": "\uae30\ubcf8 \ub2a5\ub825\uce58", "max_level_short": "\ucd5c\ub300 Lv.80",
        "base_hp": "\uae30\ubcf8 HP", "base_atk": "\uae30\ubcf8 \uacf5\uaca9\ub825", "base_def": "\uae30\ubcf8 \ubc29\uc5b4\ub825", "base_spd": "\uae30\ubcf8 \uc18d\ub3c4",
        "taunt": "\ub3c4\ubc1c \uc218\uce58", "max_energy": "\ucd5c\ub300 \uc5d0\ub108\uc9c0", "trace_stat_bonus": "\ud589\uc801 \ub2a5\ub825\uce58 \ubcf4\ub108\uc2a4",
        "voice_cast": "\uc131\uc6b0", "not_credited": "\ubbf8\ub4f1\ub85d",
    },
}


DETAIL_PUNCT = re.compile(r"^[,.;:!?%\u2026\)\]\}\u2019\u201d]+$")


REMOVED_COLOR = (224, 150, 164, 255)


ADDED_COLOR = (142, 216, 168, 255)


ARROW_COLOR = (150, 138, 175, 255)


BONUS_ICONS = {
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
}


BASIC_STAT_ICONS = {
    "hp": "IconMaxHP.webp",
    "atk": "IconAttack.webp",
    "def": "IconDefence.webp",
    "spd": "IconSpeed.webp",
}
