# HoYoLAB models

Field names and defaults below reflect the repository code. `Required` means the provider/model constructor must supply that field; optional fields show their default. Pydantic models support `model_validate(payload)`, `model_dump()`, and `model_dump_json()`. Use `model_dump(mode="json")` for JSON-compatible values; dataclasses instead expose their typed attributes directly.

Import the principal response models from `hsr_cards.providers.hoyolab.models`; compatibility exports remain under `hsr_cards.models`. Nested calendar/Currency Wars models can be imported from their respective grouped modules.

```python
from hsr_cards.models.auth import Cookies
from hsr_cards.models.notes import NotesData
from hsr_cards.models.events import CalendarData
from hsr_cards.models.currencywar import CurrencyWarData
```

Credential values must be supplied explicitly. Applications choose how to obtain them. Daily-note durations are seconds; note/calendar timestamps are Unix timestamps where documented.

## Credentials

### `Cookies`

Explicit ltoken/ltuid credentials; constructing this model performs no IO.

Fields:

- `ltoken_v2: str`: Required.
- `ltuid_v2: str`: Required.

## Daily notes

### `NotesData`

Authenticated daily-note counters for stamina, expeditions and daily/weekly progress.

Recovery duration is in seconds and stamina/current times are Unix timestamps.
Includes reserve stamina, Simulated/Divergent Universe, Currency Wars and period
score counters as supplied by HoYoLAB.

Fields:

- `current_stamina: int`: Required.
- `max_stamina: int`: Required.
- `stamina_recover_time: int`: Required.
- `stamina_full_ts: int`: Required.
- `accepted_epedition_num: int`: Required.
- `total_expedition_num: int`: Required.
- `current_train_score: int`: Required.
- `max_train_score: int`: Required.
- `current_rogue_score: int`: Required.
- `max_rogue_score: int`: Required.
- `weekly_cocoon_cnt: int`: Required.
- `weekly_cocoon_limit: int`: Required.
- `current_reserve_stamina: int`: Required.
- `is_reserve_stamina_full: bool`: Required.
- `rogue_tourn_weekly_unlocked: bool`: Required.
- `rogue_tourn_weekly_max: int`: Required.
- `rogue_tourn_weekly_cur: int`: Required.
- `current_ts: int`: Required.
- `rogue_tourn_exp_is_full: bool`: Required.
- `grid_fight_weekly_cur: int`: Required.
- `grid_fight_weekly_max: int`: Required.
- `period_score: int`: Required.
- `period_max_score: int`: Required.

### `NotesResponse`

HoYoLAB return-code/message envelope with optional validated daily-note counters.

Fields:

- `retcode: int`: Required.
- `message: str`: Required.
- `data: Optional[NotesData]`: Default: `None`.

## Calendar and events

### `TimeInfo`

Calendar window containing string timestamps, formatted start/end times and provider current time.

Fields:

- `start_ts: str`: Required.
- `end_ts: str`: Required.
- `start_time: str`: Required.
- `end_time: str`: Required.
- `now: str`: Required.

### `RewardItem`

Calendar reward identity, quantity, rarity and artwork, with an optional activity reward type.

Fields:

- `item_id: int`: Required.
- `name: str`: Required.
- `icon: str`: Required.
- `wiki_url: str`: Required.
- `num: int`: Required.
- `rarity: str`: Required.
- `reward_type: Optional[str]`: Default: `None`.

### `PoolAvatar`

Character warp-pool entry with identity, element/path types, rarity and featured-status metadata.

Fields:

- `item_id: str`: Required.
- `item_name: str`: Required.
- `icon_url: str`: Required.
- `damage_type: str`: Required.
- `rarity: str`: Required.
- `avatar_base_type: str`: Required.
- `is_forward: bool`: Required.
- `wiki_url: str`: Required.
- `item_avatar_icon_path: str`: Required.
- `damage_type_name: str`: Required.

### `PoolEquip`

Light Cone warp-pool entry with identity, path type, rarity and featured-status metadata.

Fields:

- `item_id: str`: Required.
- `item_name: str`: Required.
- `item_url: str`: Required.
- `avatar_base_type: str`: Required.
- `rarity: str`: Required.
- `is_forward: bool`: Required.
- `wiki_url: str`: Required.

### `CardPool`

A timed character/Light Cone warp pool with entries, version and future-version status.

Fields:

- `name: str`: Required.
- `type: str`: Required.
- `avatar_list: list[PoolAvatar]`: Required.
- `equip_list: list[PoolEquip]`: Required.
- `is_after_version: bool`: Required.
- `time_info: TimeInfo`: Required.
- `version: str`: Required.
- `id: str`: Required.
- `gacha_time_type: str`: Required.

### `Activity`

A timed calendar activity with player progress, rewards, completion status and drop/refresh rules.

Fields:

- `id: int`: Required.
- `version: str`: Required.
- `name: str`: Required.
- `act_type: str`: Required.
- `act_status: str`: Required.
- `reward_list: list[RewardItem]`: Required.
- `total_progress: int`: Required.
- `current_progress: int`: Required.
- `time_info: TimeInfo`: Required.
- `panel_id: int`: Required.
- `panel_desc: str`: Required.
- `strategy: str`: Required.
- `multiple_drop_type: int`: Required.
- `multiple_drop_type_list: list[int]`: Required.
- `count_refresh_type: int`: Required.
- `count_value: int`: Required.
- `drop_multiple: int`: Required.
- `is_after_version: bool`: Required.
- `sort_weight: int`: Required.
- `special_reward: Optional[RewardItem]`: Default: `None`.
- `all_finished: bool`: Required.
- `show_text: str`: Required.
- `act_time_type: str`: Required.

### `Challenge`

A timed endgame calendar cycle with challenge type, progress, rewards and AA rank artwork.

Fields:

- `group_id: int`: Required.
- `name_mi18n: str`: Required.
- `challenge_type: str`: Required.
- `total_progress: int`: Required.
- `current_progress: int`: Required.
- `status: str`: Required.
- `time_info: TimeInfo`: Required.
- `reward_list: list[RewardItem]`: Required.
- `special_reward: Optional[RewardItem]`: Default: `None`.
- `show_text: str`: Required.
- `challenge_peak_rank_icon_type: str`: Required.
- `challenge_peak_rank_icon: str`: Required.
- `challenge_peak_start_version: str`: Required.
- `extra_progress: int`: Required.

### `CalendarData`

Calendar payload grouping character/Light Cone pools, activities and challenge cycles with game time/version.

Fields:

- `avatar_card_pool_list: list[CardPool]`: Required.
- `equip_card_pool_list: list[CardPool]`: Required.
- `act_list: list[Activity]`: Required.
- `challenge_list: list[Challenge]`: Required.
- `now: str`: Required.
- `cur_game_version: str`: Required.

### `CalendarResponse`

HoYoLAB return-code/message envelope with optional validated CalendarData.

Fields:

- `retcode: int`: Required.
- `message: str`: Required.
- `data: Optional[CalendarData]`: Default: `None`.

## Currency Wars

### `CurrencyWarDivision`

Currency Wars division identity, level/promotion status and display artwork.

Fields:

- `icon: str`: Required.
- `level: str`: Required.
- `name_with_num: str`: Required.
- `name: str`: Required.
- `is_promotion: bool`: Default: `False`.
- `icon_with_bg: Optional[str]`: Default: `None`.

### `CurrencyWarBrief`

Archived run summary with time, placement, remaining HP, coin totals and division.

Fields:

- `archive_time: str`: Required.
- `archive_time_ts: str`: Required.
- `archive_rank: str`: Required.
- `remain_hp: str`: Required.
- `total_coin: str`: Required.
- `lineup_coin: str`: Required.
- `division: CurrencyWarDivision`: Required.

### `CurrencyWarHistorySeason`

Past Currency Wars season with season/division levels, name and artwork.

Fields:

- `season_id: str`: Required.
- `season_level: str`: Required.
- `division_level: str`: Required.
- `division_name: str`: Required.
- `icon: str`: Required.
- `icon_with_bg: Optional[str]`: Default: `None`.

### `CurrencyWarSeason`

Current Currency Wars division, weekly score, unlock/progress flags and season history.

Fields:

- `division: CurrencyWarDivision`: Required.
- `season_level: str`: Required.
- `weekly_score_cur: str`: Required.
- `weekly_score_max: str`: Required.
- `unlocked: bool`: Required.
- `has_played: bool`: Required.
- `handbook_progress: str`: Required.
- `trait_progress: str`: Required.
- `quest_cur: str`: Required.
- `quest_max: str`: Required.
- `history_season_list: list[CurrencyWarHistorySeason]`: Default: `[]`.

### `CurrencyWarEquip`

One equipped Currency Wars item with category, name, icon and optional wiki link.

Fields:

- `equip_id: str`: Required.
- `icon: str`: Required.
- `category: str`: Required.
- `name: str`: Required.
- `wiki_url: str`: Default: `''`.

### `CurrencyWarRole`

One front/back lineup unit with position, rank, equipment and trial/upgrade/projection flags.

Fields:

- `role_id: str`: Required.
- `avatar_id: str`: Required.
- `icon: str`: Required.
- `star: str`: Required.
- `rarity: str`: Required.
- `is_trial: bool`: Required.
- `is_upgrade: bool`: Required.
- `equip_list: list[CurrencyWarEquip]`: Default: `[]`.
- `pos: str`: Required.
- `role_type: str`: Required.
- `name: str`: Required.
- `is_projection: bool`: Required.
- `wiki_url: str`: Default: `''`.

### `CurrencyWarPortal`

One selected Currency Wars portal with identifier, display name and artwork.

Fields:

- `portal_id: str`: Required.
- `icon: str`: Required.
- `name: str`: Required.
- `wiki_url: str`: Default: `''`.

### `CurrencyWarAugment`

One selected Currency Wars augment with identifier, display name, quality and artwork.

Fields:

- `augment_id: str`: Required.
- `icon: str`: Required.
- `name: str`: Required.
- `quality: str`: Required.
- `wiki_url: str`: Default: `''`.

### `CurrencyWarTrait`

An active lineup trait with unit count, name, quality, type and artwork.

Fields:

- `trait_id: str`: Required.
- `icon: str`: Required.
- `trait_count: str`: Required.
- `trait_name: str`: Required.
- `quality: str`: Required.
- `trait_type: str`: Required.
- `wiki_url: str`: Default: `''`.

### `CurrencyWarDamage`

Reported damage amount/type for a Currency Wars unit or contribution identifier.

Fields:

- `damage_type: str`: Required.
- `id: str`: Required.
- `damage: str`: Required.

### `CurrencyWarSpotlight`

One lineup spotlight linked to its unit, with display artwork and optional description.

Fields:

- `spot_light_id: str`: Required.
- `role_id: str`: Required.
- `icon: str`: Required.
- `name: str`: Required.
- `desc: str`: Default: `''`.
- `role_icon: Optional[str]`: Default: `None`.

### `CurrencyWarLineup`

A complete run lineup with front/back units, portals, augments, traits, damage and spotlights.

Fields:

- `front_roles: list[CurrencyWarRole]`: Default: `[]`.
- `back_roles: list[CurrencyWarRole]`: Default: `[]`.
- `portal_list: list[CurrencyWarPortal]`: Default: `[]`.
- `augment_list: list[CurrencyWarAugment]`: Default: `[]`.
- `trait_list: list[CurrencyWarTrait]`: Default: `[]`.
- `damage_list: list[CurrencyWarDamage]`: Default: `[]`.
- `spot_light_list: list[CurrencyWarSpotlight]`: Default: `[]`.

### `CurrencyWarRun`

One archived Currency Wars run, pairing archive type and summary with the full lineup.

Fields:

- `archive_type: str`: Required.
- `brief: CurrencyWarBrief`: Required.
- `lineup: CurrencyWarLineup`: Required.

### `CurrencyWarData`

Currency Wars payload with optional current-season progress and API-ordered archived runs.

Fields:

- `grid_fight_brief: Optional[CurrencyWarSeason]`: Default: `None`.
- `grid_fight_archive_list: list[CurrencyWarRun]`: Default: `[]`.

### `CurrencyWarResponse`

HoYoLAB return-code/message envelope with optional validated CurrencyWarData.

Fields:

- `retcode: int`: Required.
- `message: str`: Required.
- `data: Optional[CurrencyWarData]`: Default: `None`.
