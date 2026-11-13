from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from .constants import PATH_ALIASES, RARITY_MAP
from .locales import DEFAULT_LOCALE, Locale


class NanokaModel(BaseModel):
    """Tolerant base model: new upstream keys are retained, never rejected."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class LocalizedText(NanokaModel):
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None

    def get(self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True) -> str | None:
        return localized_field(
            self, locale, "en", "zh", "ja", "ko", fallback=fallback
        )


class NamedEntry(NanokaModel):
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    param: list[float | int] = Field(default_factory=list)
    param_list: list[float | int] = Field(default_factory=list)


class MaterialCost(NanokaModel):
    item_id: int
    item_num: int
    rarity: str | None = None


class CharacterSummary(NanokaModel):
    id: int
    release: int | None = None
    icon: str | None = None
    rank: str | None = None
    base_type: str | None = Field(default=None, alias="baseType")
    damage_type: str | None = Field(default=None, alias="damageType")
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    desc: str | None = None
    enhance: list[Any] = Field(default_factory=list)

    @computed_field
    @property
    def name(self) -> str | None:
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def stars(self) -> int | None:
        return parse_rarity(self.rank)

    @computed_field
    @property
    def path(self) -> str | None:
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        return normalize_path_codename(self.base_type)

    @computed_field
    @property
    def element(self) -> str | None:
        return (self.damage_type or "").lower() or None

    @computed_field
    @property
    def released(self) -> bool:
        return self.release is not None

    @computed_field
    @property
    def is_beta(self) -> bool:
        return self.release is None

    @computed_field
    @property
    def release_datetime(self) -> datetime | None:
        return unix_datetime(self.release)

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CharacterSummary":
        return cls.model_validate({"id": int(identifier), **payload})


class LightConeSummary(NanokaModel):
    id: int
    rank: str | None = None
    base_type: str | None = Field(default=None, alias="baseType")
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    atk: float | int | None = None
    desc: str | None = None

    @computed_field
    @property
    def name(self) -> str | None:
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def stars(self) -> int | None:
        return parse_rarity(self.rank)

    @computed_field
    @property
    def path(self) -> str | None:
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        return normalize_path_codename(self.base_type)

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "LightConeSummary":
        return cls.model_validate({"id": int(identifier), **payload})


class RelicSetEffect(NanokaModel):
    pieces: int
    desc: str | None = None
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    param_list: list[float | int] = Field(default_factory=list, alias="ParamList")

    def display_desc(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        return self.desc or localized_field(
            self, locale, "en", "zh", "ja", "ko", fallback=fallback
        )

    @computed_field
    @property
    def description(self) -> str | None:
        return self.display_desc()


class RelicSetSummary(NanokaModel):
    id: int
    icon: str | None = None
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    set: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @computed_field
    @property
    def name(self) -> str | None:
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def effects(self) -> list[RelicSetEffect]:
        result: list[RelicSetEffect] = []
        for key in sorted(self.set, key=lambda value: int(value) if str(value).isdigit() else 999):
            payload = dict(self.set[key])
            payload.setdefault("pieces", int(key) if str(key).isdigit() else 0)
            result.append(RelicSetEffect.model_validate(payload))
        return result

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "RelicSetSummary":
        return cls.model_validate({"id": int(identifier), **payload})

class MonsterSummary(NanokaModel):
    id: int
    rank: str | None = None
    camp: int | None = None
    icon: str | None = None
    child: list[int] = Field(default_factory=list)
    weak: list[str] = Field(default_factory=list)
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    desc: str | None = None

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @computed_field
    @property
    def name(self) -> str | None:
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def weaknesses(self) -> list[str]:
        return [weakness.lower() for weakness in self.weak]

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "MonsterSummary":
        return cls.model_validate({"id": int(identifier), **payload})


class MonsterStats(NanokaModel):
    id: int | None = None
    rank: str | None = Field(default=None, alias="Rank")
    attack_base: float | int | None = Field(default=None, alias="AttackBase")
    defence_base: float | int | None = Field(default=None, alias="DefenceBase")
    hp_base: float | int | None = Field(default=None, alias="HPBase")
    speed_base: float | int | None = Field(default=None, alias="SpeedBase")
    stance_base: float | int | None = Field(default=None, alias="StanceBase")
    status_resistance_base: float | None = Field(default=None, alias="StatusResistanceBase")
    child: list[dict[str, Any]] = Field(default_factory=list)


class MazeSchedule(NanokaModel):
    id: int
    name: str | None = None
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None
    begin: str | None = None
    end: str | None = None
    live_begin: str | None = None
    live_end: str | None = None
    param: list[float | int] = Field(default_factory=list)
    mode: str | None = None
    version: str | None = None

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        if self.name:
            return self.name
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @computed_field
    @property
    def localized_name(self) -> str | None:
        return self.display_name()

    @computed_field
    @property
    def live_begins_at(self) -> datetime | None:
        return parse_datetime(self.live_begin)

    @computed_field
    @property
    def live_ends_at(self) -> datetime | None:
        return parse_datetime(self.live_end)

    @computed_field
    @property
    def begins_at(self) -> datetime | None:
        return self.live_begins_at or parse_datetime(self.begin)

    @computed_field
    @property
    def ends_at(self) -> datetime | None:
        return self.live_ends_at or parse_datetime(self.end)

    @computed_field
    @property
    def has_live_window(self) -> bool:
        return bool(self.live_begin and self.live_end)

    @computed_field
    @property
    def test_begins_at(self) -> datetime | None:
        return parse_datetime(self.begin)

    @computed_field
    @property
    def test_ends_at(self) -> datetime | None:
        return parse_datetime(self.end)

    @computed_field
    @property
    def is_live(self) -> bool:
        return self.is_live_at()

    @computed_field
    @property
    def is_upcoming(self) -> bool:
        return bool(self.begins_at and self.begins_at > as_utc())

    @computed_field
    @property
    def has_schedule(self) -> bool:
        return self.begins_at is not None or self.ends_at is not None

    def is_live_at(self, when: datetime | None = None) -> bool:
        moment = as_utc(when)
        starts, ends = self.begins_at, self.ends_at
        return bool(starts and ends and starts <= moment <= ends)

    @classmethod
    def from_entry(
        cls,
        identifier: str | int,
        payload: dict[str, Any],
        *,
        mode: str | None = None,
        version: str | None = None,
    ) -> "MazeSchedule":
        return cls.model_validate(
            {"id": int(identifier), "mode": mode, "version": version, **payload}
        )


class PeakSchedule(MazeSchedule):
    """Anomaly Arbitration seasons are ordered but have no date window."""


class StageConfigValue(NanokaModel):
    key: str | None = Field(default=None, alias="jdkamoanicm")
    value: str | None = Field(default=None, alias="mojjbfbkbnc")


class MonsterSlot(NanokaModel):
    monster0: int | None = None
    monster1: int | None = None
    monster2: int | None = None
    monster3: int | None = None
    monster4: int | None = None

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        return [
            value
            for value in (
                self.monster0,
                self.monster1,
                self.monster2,
                self.monster3,
                self.monster4,
            )
            if value is not None
        ]


class StageInvasion(NanokaModel):
    monster_list: list[MonsterSlot] = Field(default_factory=list)
    monster_ids: list[int] = Field(default_factory=list)

    @computed_field
    @property
    def all_monster_ids(self) -> list[int]:
        found = list(self.monster_ids)
        found.extend(monster for slot in self.monster_list for monster in slot.monster_ids)
        return list(dict.fromkeys(found))


class StageMonster(NanokaModel):
    id: int | None = None
    level: int | None = None
    monster_id: int | None = None

    @computed_field
    @property
    def resolved_id(self) -> int | None:
        return self.monster_id or self.id


class StageEvent(NanokaModel):
    stage_id: int | None = None
    stage_type: str | None = None
    stage_name: str | int | None = None
    hard_level_group: int | None = None
    level: int | None = None
    elite_group: int | None = None
    max_teammate_count: int | None = None
    monster_list: list[MonsterSlot] = Field(default_factory=list)
    stage_config_data: list[StageConfigValue] = Field(default_factory=list)
    invasion: StageInvasion | None = None
    # Some generated payloads expose a flat ``monsters`` list in addition to
    # the wave-shaped ``monster_list``.
    monster_ids: list[int] = Field(default_factory=list)
    release: bool | None = None

    @computed_field
    @property
    def all_monster_ids(self) -> list[int]:
        found = list(self.monster_ids)
        for slot in self.monster_list:
            found.extend(slot.monster_ids)
        if self.invasion:
            found.extend(self.invasion.all_monster_ids)
        return list(dict.fromkeys(found))

    @computed_field
    @property
    def wave_count(self) -> int:
        return len(self.monster_list)


class InfiniteWave(NanokaModel):
    infinite_wave_id: int | None = None
    monster_group_id_list: list[int] = Field(default_factory=list)
    max_monster_count: int | None = None
    max_teammate_count: int | None = None
    ability: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    elite_group: int | None = None


class BossConfigTag(NanokaModel):
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    param: list[float | int] = Field(default_factory=list)
    param_fix: list[float | int] = Field(default_factory=list)
    skill_id: int | None = None
    child: list["BossConfigTag"] = Field(default_factory=list)


class BossPhase(NanokaModel):
    name: str | None = None
    desc: str | None = None
    answer: str | None = None
    difficulty: int | None = None
    skill_list: list[int] = Field(default_factory=list)


class BossConfig(NanokaModel):
    difficulty: int | None = None
    difficulty_list: list[int] = Field(default_factory=list)
    tag_list: list[BossConfigTag] = Field(default_factory=list)
    difficulty_guide_list: list[BossConfigTag] = Field(default_factory=list)
    text_guide_list: list[str] = Field(default_factory=list)
    phase_list: list[BossPhase] = Field(default_factory=list)

class StageChallenge(NanokaModel):
    name: str | None = None
    desc: str | None = None
    param: float | int | list[float | int] | None = None
    param_list: list[float | int] = Field(default_factory=list)

    @computed_field
    @property
    def params(self) -> list[float | int]:
        if isinstance(self.param, list):
            return self.param
        if self.param is not None:
            return list(self.param_list or [self.param])
        return list(self.param_list)


class StageLevel(NanokaModel):
    id: int | None = None
    name: str | None = None
    pre_id: int | None = None
    pre_level_id: int | None = None
    challenge: list[StageChallenge] = Field(default_factory=list)
    challenge_special: list[StageChallenge] = Field(default_factory=list)
    countdown: int | None = None
    damage_type: list[str] = Field(default_factory=list)
    damage_type1: list[str] = Field(default_factory=list)
    damage_type2: list[str] = Field(default_factory=list)
    boss_monster_id: int | None = None
    boss_monster_id1: int | None = None
    boss_monster_id2: int | None = None
    boss_monster_id_skill_list: list[int] = Field(default_factory=list)
    boss_monster_id1_skill_list: list[int] = Field(default_factory=list)
    boss_monster_id2_skill_list: list[int] = Field(default_factory=list)
    boss_monster_config: BossConfig | None = None
    boss_monster_config1: BossConfig | None = None
    boss_monster_config2: BossConfig | None = None
    event_id_list: list[StageEvent] = Field(default_factory=list)
    event_id_list1: list[StageEvent] = Field(default_factory=list)
    event_id_list2: list[StageEvent] = Field(default_factory=list)
    infinite_list: dict[str, InfiniteWave] = Field(default_factory=dict)
    infinite_list1: dict[str, InfiniteWave] = Field(default_factory=dict)
    infinite_list2: dict[str, InfiniteWave] = Field(default_factory=dict)
    npc_monster_id_list: list[int] = Field(default_factory=list)
    npc_monster_id_list1: list[int] = Field(default_factory=list)
    npc_monster_id_list2: list[int] = Field(default_factory=list)
    maze_group_id1: int | None = None
    maze_group_id2: int | None = None
    tag_list: list[NamedEntry] = Field(default_factory=list)

    @computed_field
    @property
    def boss_ids(self) -> list[int]:
        found = [
            value
            for value in (self.boss_monster_id, self.boss_monster_id1, self.boss_monster_id2)
            if value is not None
        ]
        return list(dict.fromkeys(found))

    @computed_field
    @property
    def events(self) -> list[StageEvent]:
        events = list(self.event_id_list)
        events.extend(self.event_id_list1)
        events.extend(self.event_id_list2)
        return events

    @computed_field
    @property
    def all_events(self) -> list[StageEvent]:
        return self.events

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        found: list[int] = list(self.boss_ids)
        found.extend(self.npc_monster_id_list)
        found.extend(self.npc_monster_id_list1)
        found.extend(self.npc_monster_id_list2)
        for event in self.events:
            found.extend(event.all_monster_ids)
        for wave in self.infinite_waves:
            found.extend(wave.monster_group_id_list)
        return list(dict.fromkeys(value for value in found if value))

    @computed_field
    @property
    def all_monster_ids(self) -> list[int]:
        return self.monster_ids

    @computed_field
    @property
    def infinite_waves(self) -> list[InfiniteWave]:
        waves: list[InfiniteWave] = []
        for mapping in (self.infinite_list, self.infinite_list1, self.infinite_list2):
            waves.extend(mapping.values())
        return waves

    @computed_field
    @property
    def elements(self) -> list[str]:
        found = list(self.damage_type) + list(self.damage_type1) + list(self.damage_type2)
        return list(dict.fromkeys(value.lower() for value in found if value))

    @field_validator("challenge", "challenge_special", mode="before")
    @classmethod
    def _accept_challenge_dict(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return [value]
        return value


class EndgameDetail(NanokaModel):
    id: int | None = None
    name: str | None = None
    buff: NamedEntry | None = None
    buff_list: list[NamedEntry] = Field(default_factory=list)
    buff_list1: list[NamedEntry] = Field(default_factory=list)
    buff_list2: list[NamedEntry] = Field(default_factory=list)
    buff_list3: list[NamedEntry] = Field(default_factory=list)
    option: list[NamedEntry] = Field(default_factory=list)
    sub_option: list[NamedEntry] = Field(default_factory=list)
    begin_time: str | None = None
    end_time: str | None = None
    level: list[StageLevel] = Field(default_factory=list)
    mode: str | None = None

    @computed_field
    @property
    def stages(self) -> list[StageLevel]:
        return self.level

    @computed_field
    @property
    def boss_stage(self) -> StageLevel | None:
        candidates = [
            stage
            for stage in self.level
            if stage.boss_ids and any(event.all_monster_ids for event in stage.events)
        ]
        if candidates:
            return candidates[-1]
        non_empty = [
            stage for stage in self.level if stage.boss_ids or any(event.all_monster_ids for event in stage.events)
        ]
        return non_empty[-1] if non_empty else None

    @computed_field
    @property
    def boss_ids(self) -> list[int]:
        stage = self.boss_stage
        return stage.boss_ids if stage else []

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        found: list[int] = []
        for stage in self.level:
            found.extend(stage.monster_ids)
        return list(dict.fromkeys(found))

    @computed_field
    @property
    def starts_at(self) -> datetime | None:
        return parse_datetime(self.begin_time)

    @computed_field
    @property
    def ends_at(self) -> datetime | None:
        return parse_datetime(self.end_time)

    @computed_field
    @property
    def is_live(self) -> bool:
        start, end = self.starts_at, self.ends_at
        return bool(start and end and start <= as_utc() <= end)

    @field_validator("level", mode="before")
    @classmethod
    def _accept_stage_dict(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return [value]
        return value


class PeakBossLevel(StageLevel):
    pass


class PeakDetail(NanokaModel):
    id: int | None = None
    name: str | None = None
    pre_level: list[StageLevel] = Field(default_factory=list)
    boss_level: StageLevel | None = None
    boss_config: BossConfig | None = None
    mode: str | None = None

    @computed_field
    @property
    def stages(self) -> list[StageLevel]:
        return [*self.pre_level, *([self.boss_level] if self.boss_level else [])]

    @computed_field
    @property
    def boss_stage(self) -> StageLevel | None:
        return self.boss_level

    @computed_field
    @property
    def boss_ids(self) -> list[int]:
        return self.boss_level.boss_ids if self.boss_level else []

    @computed_field
    @property
    def boss_name(self) -> str | None:
        return self.boss_level.name if self.boss_level else self.name

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        found: list[int] = list(self.boss_ids)
        for stage in self.pre_level:
            found.extend(stage.monster_ids)
        if self.boss_level:
            found.extend(self.boss_level.monster_ids)
        return list(dict.fromkeys(found))


class EliteGroup(NanokaModel):
    elite_group: int = Field(alias="EliteGroup")
    attack_ratio: float = Field(default=1, alias="AttackRatio")
    defence_ratio: float = Field(default=1, alias="DefenceRatio")
    hp_ratio: float = Field(default=1, alias="HPRatio")
    speed_ratio: float = Field(default=1, alias="SpeedRatio")
    stance_ratio: float = Field(default=1, alias="StanceRatio")


class HardLevelGroup(NanokaModel):
    hard_level_group: int = Field(alias="HardLevelGroup")
    level: int = Field(alias="Level")
    attack_ratio: float = Field(default=1, alias="AttackRatio")
    defence_ratio: float = Field(default=1, alias="DefenceRatio")
    hp_ratio: float = Field(default=1, alias="HPRatio")
    speed_ratio: float = Field(default=1, alias="SpeedRatio")
    stance_ratio: float = Field(default=1, alias="StanceRatio")
    combat_power_list: list[float | int] = Field(default_factory=list, alias="CombatPowerList")


class InfiniteEliteGroup(EliteGroup):
    pass

class RefinementLevel(NanokaModel):
    level: int | None = None
    param_list: list[float | int] = Field(default_factory=list)


class LightConeRefinement(NanokaModel):
    name: str | None = None
    desc: str | None = None
    level: dict[str, RefinementLevel] = Field(default_factory=dict)

    @computed_field
    @property
    def levels(self) -> dict[int, list[float | int]]:
        return {
            int(key): value.param_list
            for key, value in self.level.items()
            if str(key).isdigit()
        }


class PromotionCost(MaterialCost):
    pass


class LightConeStat(NanokaModel):
    equipment_id: int
    promotion: int | None = None
    promotion_cost_list: list[PromotionCost] = Field(default_factory=list)
    player_level_require: int | None = None
    world_level_require: int | None = None
    max_level: int | None = None
    base_hp: float | None = None
    base_hp_add: float | None = None
    base_attack: float | None = None
    base_attack_add: float | None = None
    base_defence: float | None = None
    base_defence_add: float | None = None


class LightConeDetail(NanokaModel):
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    base_type: str | None = None
    refinements: LightConeRefinement | None = None
    stats: list[LightConeStat] = Field(default_factory=list)

    @computed_field
    @property
    def stars(self) -> int | None:
        return parse_rarity(self.rarity)

    @computed_field
    @property
    def path(self) -> str | None:
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        return normalize_path_codename(self.base_type)


class CharacterRank(NanokaModel):
    id: int
    name: str | None = None
    desc: str | None = None
    icon: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class SkillLevel(NanokaModel):
    level: int | None = None
    param_list: list[float | int] = Field(default_factory=list)


class SkillExtra(NanokaModel):
    name: str | None = None
    desc: str | None = None
    param: list[float | int] = Field(default_factory=list)
    param_list: list[float | int] = Field(default_factory=list)


class CharacterSkill(NanokaModel):
    id: int
    name: str | None = None
    desc: str | None = None
    simple_desc: str | None = None
    type: str | None = None
    type_name: str | None = None
    tag: str | None = None
    sp_base: int | None = None
    bp_need: int | None = None
    bp_add: int | None = None
    show_stance_list: list[float | int] = Field(default_factory=list)
    skill_combo_value_delta: float | None = None
    related_ex_rank_id_list: list[int] = Field(default_factory=list)
    extra: dict[str, SkillExtra] = Field(default_factory=dict)
    level: dict[str, SkillLevel] = Field(default_factory=dict)

    def params_at(self, level: int) -> list[float | int] | None:
        entry = self.level.get(str(level))
        return entry.param_list if entry else None

    @computed_field
    @property
    def max_level(self) -> int | None:
        levels = [int(key) for key in self.level if str(key).isdigit()]
        return max(levels) if levels else None

    @computed_field
    @property
    def is_attack(self) -> bool:
        return self.type in {"Normal", "BPSkill", "Ultra", "Maze", "Talent"}


class SkillTreeLevel(NanokaModel):
    anchor: str | None = None
    avatar_promotion_limit: int | None = None
    avatar_level_limit: int | None = None
    default_unlock: bool = False
    icon: str | None = None
    level_up_skill_id: list[int] = Field(default_factory=list)
    material_list: list[MaterialCost] = Field(default_factory=list)
    max_level: int | None = None
    param_list: list[float | int] = Field(default_factory=list)
    point_id: int | None = None
    point_name: str | None = None
    point_desc: str | None = None
    # Older builds publish a label here ("PointNormal"); newer builds use an int.
    point_trigger_key: int | str | None = None
    point_type: int | None = None
    pre_point: list[str | int] = Field(default_factory=list)
    status_add_list: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class CharacterTrace(NanokaModel):
    point: str
    levels: list[SkillTreeLevel] = Field(default_factory=list)

    @computed_field
    @property
    def point_type(self) -> int | None:
        return next((level.point_type for level in self.levels if level.point_type is not None), None)

    @computed_field
    @property
    def is_bonus_ability(self) -> bool:
        return self.point_type == 3

    @computed_field
    @property
    def is_major_trace(self) -> bool:
        return self.point_type == 2

    @computed_field
    @property
    def is_minor_trace(self) -> bool:
        return self.point_type == 1

    @computed_field
    @property
    def name(self) -> str | None:
        return next((level.point_name for level in self.levels if level.point_name), None)

    @computed_field
    @property
    def description(self) -> str | None:
        return next((level.point_desc for level in self.levels if level.point_desc), None)

    @computed_field
    @property
    def icon(self) -> str | None:
        return next((level.icon for level in self.levels if level.icon), None)


class VoiceActors(NanokaModel):
    chinese: str | None = None
    japanese: str | None = None
    korean: str | None = None
    english: str | None = None


class CharacterInfo(NanokaModel):
    camp: str | None = None
    va: VoiceActors = Field(default_factory=VoiceActors)
    stories: dict[str, str | None] = Field(default_factory=dict)
    voicelines: list[dict[str, Any]] = Field(default_factory=list)


class CharacterStat(NanokaModel):
    attack_base: float | None = None
    attack_add: float | None = None
    defence_base: float | None = None
    defence_add: float | None = None
    hp_base: float | None = None
    hp_add: float | None = None
    speed_base: float | None = None
    critical_chance: float | None = None
    critical_damage: float | None = None
    base_aggro: float | None = None
    cost: list[MaterialCost] = Field(default_factory=list)
    promotion: int | None = None

    @computed_field
    @property
    def attack(self) -> float | None:
        return sum_optional(self.attack_base, self.attack_add)

    @computed_field
    @property
    def defence(self) -> float | None:
        return sum_optional(self.defence_base, self.defence_add)

    @computed_field
    @property
    def hp(self) -> float | None:
        return sum_optional(self.hp_base, self.hp_add)


class CharacterRelicBuild(NanokaModel):
    avatar_id: int | None = None
    set4_id_list: list[int] = Field(default_factory=list)
    set2_id_list: list[int] = Field(default_factory=list)
    property_list3: list[str] = Field(default_factory=list)
    property_list4: list[str] = Field(default_factory=list)
    property_list5: list[str] = Field(default_factory=list)
    property_list6: list[str] = Field(default_factory=list)
    property_list: list[dict[str, Any]] = Field(default_factory=list)
    sub_affix_property_list: list[str] = Field(default_factory=list)
    score_rank_list: list[float | int] = Field(default_factory=list)

    @computed_field
    @property
    def main_stats(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for entry in self.property_list:
            relic_type = entry.get("relic_type")
            prop = entry.get("property_type")
            if relic_type and prop:
                result.setdefault(str(relic_type), []).append(str(prop))
        return result

    @computed_field
    @property
    def primary_set(self) -> int | None:
        return self.set4_id_list[0] if self.set4_id_list else None

    @computed_field
    @property
    def planar_set(self) -> int | None:
        return self.set2_id_list[0] if self.set2_id_list else None


class CharacterTeam(NanokaModel):
    avatar_id: int | None = None
    team_id: int | None = None
    position: int | None = None
    member_list: list[int] = Field(default_factory=list)
    backup_list1: list[int] = Field(default_factory=list)
    backup_list2: list[int] = Field(default_factory=list)
    backup_list3: list[int] = Field(default_factory=list)
    backup_group_list1: list[Any] = Field(default_factory=list)
    backup_group_list2: list[Any] = Field(default_factory=list)
    backup_group_list3: list[Any] = Field(default_factory=list)

    @computed_field
    @property
    def members(self) -> list[int]:
        return [self.avatar_id, *self.member_list] if self.avatar_id else list(self.member_list)


class CharacterDetail(NanokaModel):
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    chara_info: CharacterInfo = Field(default_factory=CharacterInfo)
    rarity: str | None = None
    avatar_vo_tag: str | None = None
    sp_need: int | None = None
    base_type: str | None = None
    damage_type: str | None = None
    ranks: dict[str, CharacterRank] = Field(default_factory=dict)
    ex_ranks: dict[str, CharacterRank] = Field(default_factory=dict)
    skills: dict[str, CharacterSkill] = Field(default_factory=dict)
    skill_trees: dict[str, dict[str, SkillTreeLevel]] = Field(default_factory=dict)
    enhanced: dict[str, Any] = Field(default_factory=dict)
    memosprite: dict[str, Any] = Field(default_factory=dict)
    unique: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, CharacterStat] = Field(default_factory=dict)
    relics: CharacterRelicBuild | None = None
    lightcones: list[int] = Field(default_factory=list)
    teams: list[CharacterTeam] = Field(default_factory=list)
    skin: dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def stars(self) -> int | None:
        return parse_rarity(self.rarity)

    @computed_field
    @property
    def path(self) -> str | None:
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        return normalize_path_codename(self.base_type)

    @computed_field
    @property
    def element(self) -> str | None:
        return (self.damage_type or "").lower() or None

    @computed_field
    @property
    def eidolons(self) -> list[CharacterRank]:
        return sorted(
            self.ranks.values(),
            key=lambda rank: int(rank.id) if str(rank.id).isdigit() else 0,
        )

    @computed_field
    @property
    def extra_ranks(self) -> list[CharacterRank]:
        return sorted(self.ex_ranks.values(), key=lambda rank: rank.id)

    @computed_field
    @property
    def traces(self) -> list[CharacterTrace]:
        result: list[CharacterTrace] = []
        for point, levels in self.skill_trees.items():
            ordered = [
                level
                for _, level in sorted(
                    levels.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0
                )
            ]
            result.append(CharacterTrace(point=point, levels=ordered))
        return result

    @computed_field
    @property
    def bonus_abilities(self) -> list[CharacterTrace]:
        return [trace for trace in self.traces if trace.is_bonus_ability]

    @computed_field
    @property
    def major_traces(self) -> list[CharacterTrace]:
        return [trace for trace in self.traces if trace.is_major_trace]

    @computed_field
    @property
    def minor_traces(self) -> list[CharacterTrace]:
        return [trace for trace in self.traces if trace.is_minor_trace]

    @computed_field
    @property
    def max_stat(self) -> CharacterStat | None:
        if not self.stats:
            return None
        key = max(self.stats, key=lambda value: int(value) if str(value).isdigit() else -1)
        return self.stats[key]

    @computed_field
    @property
    def basic_attack(self) -> CharacterSkill | None:
        return next(
            (skill for skill in self.skills.values() if skill.type == "Normal"),
            None,
        )

    @computed_field
    @property
    def skill(self) -> CharacterSkill | None:
        return next(
            (skill for skill in self.skills.values() if skill.type == "BPSkill"),
            None,
        )

    @computed_field
    @property
    def ultimate(self) -> CharacterSkill | None:
        return next(
            (skill for skill in self.skills.values() if skill.type == "Ultra"),
            None,
        )

    @computed_field
    @property
    def talent(self) -> CharacterSkill | None:
        return next(
            (skill for skill in self.skills.values() if skill.type_name == "Talent"),
            None,
        )

    @computed_field
    @property
    def technique(self) -> CharacterSkill | None:
        return next(
            (skill for skill in self.skills.values() if skill.type == "Maze"),
            None,
        )

    @computed_field
    @property
    def enhanced_skills(self) -> list[CharacterSkill]:
        return [
            skill
            for skill in self.skills.values()
            if skill.type is None and skill.type_name is None
        ]

class MonsterVariant(NanokaModel):
    id: int
    attack_modify_ratio: float | None = None
    defence_modify_ratio: float | None = None
    elite_group: int | None = None
    hp_modify_ratio: float | None = None
    speed_modify_ratio: float | None = None
    speed_modify_value: float | None = None
    stance_modify_ratio: float | None = None
    stance_modify_value: float | None = None
    stance_weak_list: list[str] = Field(default_factory=list)
    hard_level_group: int | None = None
    damage_type_resistance: list[dict[str, Any]] = Field(default_factory=list)
    skill_list: list[dict[str, Any] | int] = Field(default_factory=list)


class MonsterDetail(NanokaModel):
    id: int
    name: str | None = None
    desc: str | None = None
    monster_camp_id: int | None = None
    attack_base: float | None = None
    critical_damage_base: float | None = None
    defence_base: float | None = None
    hp_base: float | None = None
    initial_delay_ratio: float | None = None
    image_path: str | None = None
    minimum_fatigue_ratio: float | None = None
    rank: str | None = None
    speed_base: float | None = None
    stance_base: float | None = None
    stance_count: int | None = None
    status_resistance_base: float | None = None
    child: list[MonsterVariant] = Field(default_factory=list)
    drop: list[Any] = Field(default_factory=list)

    @computed_field
    @property
    def weaknesses(self) -> list[str]:
        if self.child:
            return [weakness.lower() for weakness in self.child[0].stance_weak_list]
        return []

    @computed_field
    @property
    def variants(self) -> list[MonsterVariant]:
        return self.child


class RelicPart(NanokaModel):
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    story: str | None = None
    icon: str | None = None

    @computed_field
    @property
    def slot(self) -> str | None:
        return RELIC_SLOT_BY_ID.get(self.id or 0)


class RelicSetEffectDetail(NanokaModel):
    pieces: int
    desc: str | None = None
    param_list: list[float | int] = Field(default_factory=list)


class RelicSetDetail(NanokaModel):
    id: int | None = None
    name: str | None = None
    icon: str | None = None
    parts: dict[str, RelicPart] = Field(default_factory=dict)
    require_num: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @computed_field
    @property
    def effects(self) -> list[RelicSetEffectDetail]:
        result: list[RelicSetEffectDetail] = []
        for key in sorted(
            self.require_num, key=lambda value: int(value) if str(value).isdigit() else 999
        ):
            data = self.require_num[key]
            result.append(
                RelicSetEffectDetail(
                    pieces=int(key) if str(key).isdigit() else 0,
                    desc=data.get("desc"),
                    param_list=data.get("param_list") or data.get("ParamList") or [],
                )
            )
        return result

    @computed_field
    @property
    def piece_list(self) -> list[RelicPart]:
        result: list[RelicPart] = []
        for key, part in self.parts.items():
            if part.id is None and str(key).isdigit():
                part = part.model_copy(update={"id": int(key)})
            result.append(part)
        return result


class ItemSummary(NanokaModel):
    id: int
    item_name: str | None = None
    item_sub_type: str | None = None
    item_main_type: str | None = None
    purpose_type: int | None = None
    rarity: str | None = None
    item_icon_path: str | None = None
    item_figure_icon_path: str | None = None
    item_currency_icon_path: str | None = None
    item_avatar_icon_path: str | None = None
    item_desc: str | None = None
    item_bg_desc: str | None = None
    pile_limit: int | None = None

    @computed_field
    @property
    def name(self) -> str | None:
        return self.item_name

    @computed_field
    @property
    def desc(self) -> str | None:
        return self.item_bg_desc or self.item_desc

    @computed_field
    @property
    def stars(self) -> int | None:
        return parse_rarity(self.rarity)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "ItemSummary":
        normalized = {snake_case(key): value for key, value in payload.items()}
        normalized.setdefault("id", int(identifier))
        return cls.model_validate(normalized)


class Achievement(NanokaModel):
    id: int
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    show_type: str | None = None
    param_list: list[float | int] = Field(default_factory=list)


class AchievementSeries(NanokaModel):
    id: int
    priority: int | None = None
    name: str | None = None
    achievements: list[Achievement] = Field(default_factory=list, alias="list")

    @computed_field
    @property
    def items(self) -> list[Achievement]:
        return self.achievements

    @computed_field
    @property
    def count(self) -> int:
        return len(self.achievements)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "AchievementSeries":
        return cls.model_validate({"id": int(identifier), **payload})


class CurrencyRole(NanokaModel):
    id: int
    name: str | None = None
    front_back_type: str | None = None
    rarity: int | None = None
    heal_or_shield_display: str | None = None
    charge_type: list[str] = Field(default_factory=list)
    max_sp_icon: str | None = None
    trait_list: list[int] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyRole":
        return cls.model_validate({"id": int(identifier), **payload})


class CurrencyTraitLayer(NanokaModel):
    id: int | None = None
    buff_name: str | None = None
    buff_desc: str | None = None
    buff_simple_desc: str | None = None
    buff_param_list: list[float | int] = Field(default_factory=list)
    quality: str | None = None
    param_list: list[float | int] = Field(default_factory=list)


class CurrencyTrait(NanokaModel):
    id: int
    activation_type: str | None = None
    icon_path: str | None = None
    name: str | None = None
    desc: str | None = None
    simple_desc: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    effect_list: list[dict[str, Any] | int] | dict[str, Any] = Field(default_factory=list)
    layer: dict[str, CurrencyTraitLayer] = Field(default_factory=dict)
    remark: dict[str, Any] | None = None
    sub_trait: dict[str, Any] | None = None

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyTrait":
        return cls.model_validate({"id": int(identifier), **payload})


class CurrencyItem(NanokaModel):
    id: int
    type: str | None = None
    name: str | None = None
    desc: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    icon_path: str | None = None
    consumable_rule: str | None = None
    if_stack: bool | None = None
    if_consume: bool | None = None

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyItem":
        return cls.model_validate({"id": int(identifier), **payload})


class CurrencyAugment(NanokaModel):
    id: int
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    icon: str | None = None
    effect_list: list[Any] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyAugment":
        normalized = {snake_case(key): value for key, value in payload.items()}
        normalized.setdefault("id", int(identifier))
        return cls.model_validate(normalized)


class CurrencyBuff(NanokaModel):
    id: int
    name: str | None = None
    desc: str | None = None
    rarity: str | None = None
    icon: str | None = None
    param_list: list[float | int] = Field(default_factory=list)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CurrencyBuff":
        normalized = {snake_case(key): value for key, value in payload.items()}
        normalized.setdefault("id", int(identifier))
        return cls.model_validate(normalized)


class AssetInfo(NanokaModel):
    key: str
    path: str
    url: str
    relative_path: str | None = None
    size: int | None = None
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    updated_at: datetime | None = None


class NanokaVersions(NanokaModel):
    """Published HSR data builds advertised by the Nanoka manifest."""

    versions: list[str] = Field(default_factory=list)
    live_server: str | None = None
    live_beta: str | None = None
    latest: str | None = None


class CacheManifest(NanokaModel):
    schema_version: int = 2
    version: str
    live_version: str | None = None
    language: Locale = DEFAULT_LOCALE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    complete: bool = False
    assets_complete: bool = False
    root_files: list[str] = Field(default_factory=list)
    detail_files: list[str] = Field(default_factory=list)
    detail_ids: dict[str, list[str]] = Field(default_factory=dict)
    assets: dict[str, AssetInfo] = Field(default_factory=dict)
    asset_failures: list[str] = Field(default_factory=list)
    validators: dict[str, dict[str, str]] = Field(default_factory=dict)

RELIC_SLOT_BY_ID: dict[int, str] = {
    1: "head",
    2: "hands",
    3: "body",
    4: "feet",
    5: "planar_sphere",
    6: "link_rope",
}


def localized_field(
    model: NanokaModel,
    locale: Locale | str,
    *keys: str,
    fallback: bool = True,
) -> str | None:
    loc = Locale.normalize(locale)
    value = getattr(model, loc.value, None)
    if value:
        return sanitize_localized_text(value)
    if fallback:
        for key in keys:
            candidate = getattr(model, key, None)
            if candidate:
                return sanitize_localized_text(candidate)
    return None


def sanitize_localized_text(value: str | None) -> str | None:
    """Strip game markup (notably Japanese ruby annotations) for display."""
    if not value:
        return value
    import re

    cleaned = re.sub(r"\{RUBY_B#[^}]*\}", "", value)
    cleaned = re.sub(r"\{RUBY_E#\}", "", cleaned)
    return cleaned.strip()


def parse_rarity(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text in RARITY_MAP:
        return RARITY_MAP[text]
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return RARITY_MAP.get(text)


def normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    codename = value.strip().lower()
    return PATH_ALIASES.get(codename, codename)


def normalize_path_codename(value: str | None) -> str | None:
    if not value:
        return None
    needle = value.strip().lower()
    reverse = {path: codename for codename, path in PATH_ALIASES.items()}
    return reverse.get(needle, needle)


def parse_element(value: str | None) -> str | None:
    return value.strip().lower() if value else None


def unix_datetime(value: int | float | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return as_utc(parsed)


def as_utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def snake_case(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index and not value[index - 1].isupper():
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def sum_optional(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


__all__ = [
    "NanokaModel",
    "LocalizedText",
    "NamedEntry",
    "MaterialCost",
    "CharacterSummary",
    "CharacterDetail",
    "CharacterInfo",
    "CharacterRank",
    "CharacterSkill",
    "CharacterStat",
    "CharacterRelicBuild",
    "CharacterTeam",
    "CharacterTrace",
    "SkillLevel",
    "SkillExtra",
    "SkillTreeLevel",
    "VoiceActors",
    "LightConeSummary",
    "LightConeDetail",
    "LightConeRefinement",
    "LightConeStat",
    "RefinementLevel",
    "PromotionCost",
    "RelicSetSummary",
    "RelicSetDetail",
    "RelicSetEffect",
    "RelicSetEffectDetail",
    "RelicPart",
    "MonsterSummary",
    "MonsterDetail",
    "MonsterVariant",
    "MonsterStats",
    "EliteGroup",
    "HardLevelGroup",
    "InfiniteEliteGroup",
    "MazeSchedule",
    "PeakSchedule",
    "StageChallenge",
    "StageConfigValue",
    "MonsterSlot",
    "StageMonster",
    "StageInvasion",
    "StageEvent",
    "InfiniteWave",
    "BossConfigTag",
    "BossPhase",
    "BossConfig",
    "StageLevel",
    "EndgameDetail",
    "PeakBossLevel",
    "PeakDetail",
    "ItemSummary",
    "Achievement",
    "AchievementSeries",
    "CurrencyItem",
    "CurrencyRole",
    "CurrencyTrait",
    "CurrencyTraitLayer",
    "CurrencyAugment",
    "CurrencyBuff",
    "AssetInfo",
    "CacheManifest",
    "RELIC_SLOT_BY_ID",
    "localized_field",
    "sanitize_localized_text",
    "parse_rarity",
    "normalize_path",
    "normalize_path_codename",
    "parse_element",
    "parse_datetime",
    "unix_datetime",
    "as_utc",
    "snake_case",
]
