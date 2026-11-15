"""Validated HoYoLAB calendar, banner, and event responses."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel




class TimeInfo(BaseModel):
    """Calendar window containing string timestamps, formatted start/end times and provider current time."""
    start_ts: str
    end_ts: str
    start_time: str
    end_time: str
    now: str


class RewardItem(BaseModel):
    """Calendar reward identity, quantity, rarity and artwork, with an optional activity reward type."""
    item_id: int
    name: str
    icon: str
    wiki_url: str
    num: int
    rarity: str
    reward_type: Optional[str] = None  # present in act_list, absent in challenge_list



class PoolAvatar(BaseModel):
    """Character warp-pool entry with identity, element/path types, rarity and featured-status metadata."""
    item_id: str
    item_name: str
    icon_url: str
    damage_type: str           # numeric string, e.g. "4" = Ice
    rarity: str                # "4" or "5"
    avatar_base_type: str      # path type numeric string
    is_forward: bool
    wiki_url: str
    item_avatar_icon_path: str
    damage_type_name: str      # e.g. "ice", "physical", "lightning"


class PoolEquip(BaseModel):
    """Light Cone warp-pool entry with identity, path type, rarity and featured-status metadata."""
    item_id: str
    item_name: str
    item_url: str
    avatar_base_type: str
    rarity: str
    is_forward: bool
    wiki_url: str


class CardPool(BaseModel):
    """A timed character/Light Cone warp pool with entries, version and future-version status."""
    name: str
    type: str                  # "CardPoolRole" | "CardPoolEquipment"
    avatar_list: list[PoolAvatar]
    equip_list: list[PoolEquip]
    is_after_version: bool
    time_info: TimeInfo
    version: str
    id: str
    gacha_time_type: str


class Activity(BaseModel):
    """A timed calendar activity with player progress, rewards, completion status and drop/refresh rules."""
    id: int
    version: str
    name: str
    act_type: str              # "ActivityTypeOther" | "ActivityTypeDouble" | "ActivityTypeSign"
    act_status: str            # e.g. "OtherActStatusUnFinish", "SignStatusFinish"
    reward_list: list[RewardItem]
    total_progress: int
    current_progress: int
    time_info: TimeInfo
    panel_id: int
    panel_desc: str
    strategy: str
    multiple_drop_type: int    # 0 = normal, 1 = double reward event
    multiple_drop_type_list: list[int]
    count_refresh_type: int
    count_value: int
    drop_multiple: int         # reward multiplier (e.g. 2)
    is_after_version: bool
    sort_weight: int
    special_reward: Optional[RewardItem] = None
    all_finished: bool
    show_text: str             # "Completed" | "Incomplete" | "Locked"
    act_time_type: str



class Challenge(BaseModel):
    """A timed endgame calendar cycle with challenge type, progress, rewards and AA rank artwork."""
    group_id: int
    name_mi18n: str
    challenge_type: str        # "ChallengeTypeStory" | "ChallengeTypePeak" | "ChallengeTypeChasm" | "ChallengeTypeBoss"
    total_progress: int
    current_progress: int
    status: str                # "challengeStatusInProgress" | "challengeStatusFinish" | "challengeStatusUnopened"
    time_info: TimeInfo
    reward_list: list[RewardItem]
    special_reward: Optional[RewardItem] = None
    show_text: str             # e.g. "11/12", "Completed", "Locked"
    challenge_peak_rank_icon_type: str
    challenge_peak_rank_icon: str
    challenge_peak_start_version: str
    extra_progress: int



class CalendarData(BaseModel):
    """Calendar payload grouping character/Light Cone pools, activities and challenge cycles with game time/version."""
    avatar_card_pool_list: list[CardPool]
    equip_card_pool_list: list[CardPool]
    act_list: list[Activity]
    challenge_list: list[Challenge]
    now: str
    cur_game_version: str


class CalendarResponse(BaseModel):
    """HoYoLAB return-code/message envelope with optional validated CalendarData."""
    retcode: int
    message: str
    data: Optional[CalendarData] = None
