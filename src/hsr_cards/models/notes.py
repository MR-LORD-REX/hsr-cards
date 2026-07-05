from pydantic import BaseModel
from typing import Optional


class NotesData(BaseModel):
    current_stamina: int
    max_stamina: int
    stamina_recover_time: int       # seconds until full
    stamina_full_ts: int            # unix ts when full
    accepted_epedition_num: int
    total_expedition_num: int
    current_train_score: int
    max_train_score: int
    current_rogue_score: int
    max_rogue_score: int
    weekly_cocoon_cnt: int
    weekly_cocoon_limit: int
    current_reserve_stamina: int
    is_reserve_stamina_full: bool
    rogue_tourn_weekly_unlocked: bool
    rogue_tourn_weekly_max: int
    rogue_tourn_weekly_cur: int
    current_ts: int
    rogue_tourn_exp_is_full: bool
    grid_fight_weekly_cur: int
    grid_fight_weekly_max: int
    period_score: int
    period_max_score: int


class NotesResponse(BaseModel):
    retcode: int
    message: str
    data: Optional[NotesData] = None
