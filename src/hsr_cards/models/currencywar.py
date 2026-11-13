from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CurrencyWarDivision(BaseModel):
    icon: str
    level: str
    name_with_num: str
    name: str
    is_promotion: bool = False
    icon_with_bg: Optional[str] = None


class CurrencyWarBrief(BaseModel):
    archive_time: str
    archive_time_ts: str
    archive_rank: str
    remain_hp: str
    total_coin: str
    lineup_coin: str
    division: CurrencyWarDivision


class CurrencyWarHistorySeason(BaseModel):
    season_id: str
    season_level: str
    division_level: str
    division_name: str
    icon: str
    icon_with_bg: Optional[str] = None


class CurrencyWarSeason(BaseModel):
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
    equip_id: str
    icon: str
    category: str
    name: str
    wiki_url: str = ""


class CurrencyWarRole(BaseModel):
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
    portal_id: str
    icon: str
    name: str
    wiki_url: str = ""


class CurrencyWarAugment(BaseModel):
    augment_id: str
    icon: str
    name: str
    quality: str
    wiki_url: str = ""


class CurrencyWarTrait(BaseModel):
    trait_id: str
    icon: str
    trait_count: str
    trait_name: str
    quality: str
    trait_type: str
    wiki_url: str = ""


class CurrencyWarDamage(BaseModel):
    damage_type: str
    id: str
    damage: str


class CurrencyWarSpotlight(BaseModel):
    spot_light_id: str
    role_id: str
    icon: str
    name: str
    desc: str = ""
    role_icon: Optional[str] = None


class CurrencyWarLineup(BaseModel):
    front_roles: list[CurrencyWarRole] = []
    back_roles: list[CurrencyWarRole] = []
    portal_list: list[CurrencyWarPortal] = []
    augment_list: list[CurrencyWarAugment] = []
    trait_list: list[CurrencyWarTrait] = []
    damage_list: list[CurrencyWarDamage] = []
    spot_light_list: list[CurrencyWarSpotlight] = []


class CurrencyWarRun(BaseModel):
    archive_type: str
    brief: CurrencyWarBrief
    lineup: CurrencyWarLineup


class CurrencyWarData(BaseModel):
    grid_fight_brief: Optional[CurrencyWarSeason] = None
    grid_fight_archive_list: list[CurrencyWarRun] = []


class CurrencyWarResponse(BaseModel):
    retcode: int
    message: str
    data: Optional[CurrencyWarData] = None