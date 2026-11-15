"""Validated HoYoLAB Currency Wars responses."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CurrencyWarDivision(BaseModel):
    """Currency Wars division identity, level/promotion status and display artwork."""
    icon: str
    level: str
    name_with_num: str
    name: str
    is_promotion: bool = False
    icon_with_bg: Optional[str] = None


class CurrencyWarBrief(BaseModel):
    """Archived run summary with time, placement, remaining HP, coin totals and division."""
    archive_time: str
    archive_time_ts: str
    archive_rank: str
    remain_hp: str
    total_coin: str
    lineup_coin: str
    division: CurrencyWarDivision


class CurrencyWarHistorySeason(BaseModel):
    """Past Currency Wars season with season/division levels, name and artwork."""
    season_id: str
    season_level: str
    division_level: str
    division_name: str
    icon: str
    icon_with_bg: Optional[str] = None


class CurrencyWarSeason(BaseModel):
    """Current Currency Wars division, weekly score, unlock/progress flags and season history."""
    division: CurrencyWarDivision
    season_level: str
    weekly_score_cur: str
    weekly_score_max: str
    unlocked: bool
    has_played: bool
    handbook_progress: str
    trait_progress: str
    quest_cur: str
    quest_max: str
    history_season_list: list[CurrencyWarHistorySeason] = []

class CurrencyWarEquip(BaseModel):
    """One equipped Currency Wars item with category, name, icon and optional wiki link."""
    equip_id: str
    icon: str
    category: str
    name: str
    wiki_url: str = ""


class CurrencyWarRole(BaseModel):
    """One front/back lineup unit with position, rank, equipment and trial/upgrade/projection flags."""
    role_id: str
    avatar_id: str
    icon: str
    star: str
    rarity: str
    is_trial: bool
    is_upgrade: bool
    equip_list: list[CurrencyWarEquip] = []
    pos: str
    role_type: str
    name: str
    is_projection: bool
    wiki_url: str = ""


class CurrencyWarPortal(BaseModel):
    """One selected Currency Wars portal with identifier, display name and artwork."""
    portal_id: str
    icon: str
    name: str
    wiki_url: str = ""


class CurrencyWarAugment(BaseModel):
    """One selected Currency Wars augment with identifier, display name, quality and artwork."""
    augment_id: str
    icon: str
    name: str
    quality: str
    wiki_url: str = ""


class CurrencyWarTrait(BaseModel):
    """An active lineup trait with unit count, name, quality, type and artwork."""
    trait_id: str
    icon: str
    trait_count: str
    trait_name: str
    quality: str
    trait_type: str
    wiki_url: str = ""


class CurrencyWarDamage(BaseModel):
    """Reported damage amount/type for a Currency Wars unit or contribution identifier."""
    damage_type: str
    id: str
    damage: str


class CurrencyWarSpotlight(BaseModel):
    """One lineup spotlight linked to its unit, with display artwork and optional description."""
    spot_light_id: str
    role_id: str
    icon: str
    name: str
    desc: str = ""
    role_icon: Optional[str] = None


class CurrencyWarLineup(BaseModel):
    """A complete run lineup with front/back units, portals, augments, traits, damage and spotlights."""
    front_roles: list[CurrencyWarRole] = []
    back_roles: list[CurrencyWarRole] = []
    portal_list: list[CurrencyWarPortal] = []
    augment_list: list[CurrencyWarAugment] = []
    trait_list: list[CurrencyWarTrait] = []
    damage_list: list[CurrencyWarDamage] = []
    spot_light_list: list[CurrencyWarSpotlight] = []


class CurrencyWarRun(BaseModel):
    """One archived Currency Wars run, pairing archive type and summary with the full lineup."""
    archive_type: str
    brief: CurrencyWarBrief
    lineup: CurrencyWarLineup


class CurrencyWarData(BaseModel):
    """Currency Wars payload with optional current-season progress and API-ordered archived runs."""
    grid_fight_brief: Optional[CurrencyWarSeason] = None
    grid_fight_archive_list: list[CurrencyWarRun] = []


class CurrencyWarResponse(BaseModel):
    """HoYoLAB return-code/message envelope with optional validated CurrencyWarData."""
    retcode: int
    message: str
    data: Optional[CurrencyWarData] = None