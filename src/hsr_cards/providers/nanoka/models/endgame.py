"""Endgame floors, waves, boss mechanics, and detail models."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import Field, computed_field, field_validator

from .common import NamedEntry, NanokaModel, as_utc, parse_datetime

class StageConfigValue(NanokaModel):
    """A stage configuration key/value pair using the provider obfuscated aliases."""
    key: str | None = Field(default=None, alias="jdkamoanicm")
    value: str | None = Field(default=None, alias="mojjbfbkbnc")

class MonsterSlot(NanokaModel):
    """One wave group containing up to five optional ordered monster slots.

    Occupied slots preserve their order and duplicates, which can represent
    multiple spawns of the same monster.
    """
    monster0: int | None = None
    monster1: int | None = None
    monster2: int | None = None
    monster3: int | None = None
    monster4: int | None = None

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        """Return occupied monster-slot IDs in slot order, retaining duplicates."""
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
    """Additional invasion monsters in slot-shaped, direct-ID, or flat-ID form.

    all_monster_ids combines the supported shapes into unique IDs in encounter order.
    """
    monster_list: list[MonsterSlot | StageMonster] = Field(default_factory=list)
    monster_ids: list[int] = Field(default_factory=list)

    @computed_field
    @property
    def all_monster_ids(self) -> list[int]:
        """Return unique monster IDs, including nested wave/invasion references."""
        found = list(self.monster_ids)
        for slot in self.monster_list:
            if isinstance(slot, StageMonster):
                found.append(slot.resolved_id)
            else:
                found.extend(slot.monster_ids)
        found = [monster for monster in found if monster is not None]
        return list(dict.fromkeys(found))

class StageMonster(NanokaModel):
    """A direct stage monster reference with optional level and base/variant IDs.

    resolved_id prefers monster_id over id; missing references remain None.
    """
    id: int | None = None
    level: int | None = None
    monster_id: int | None = None

    @computed_field
    @property
    def resolved_id(self) -> int | None:
        """Return monster_id when defined, otherwise the entry ID."""
        return self.monster_id or self.id

class StageEvent(NanokaModel):
    """A combat event with wave monsters, stage scaling, configuration, and invasion data.

    Retain both wave-shaped monster_list and optional flat monster_ids. Difficulty
    ratios are references here; card services compute final HP separately.
    """
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
        """Return unique monster IDs, including nested wave/invasion references."""
        found = list(self.monster_ids)
        for slot in self.monster_list:
            found.extend(slot.monster_ids)
        if self.invasion:
            found.extend(self.invasion.all_monster_ids)
        return list(dict.fromkeys(found))

    @computed_field
    @property
    def wave_count(self) -> int:
        """Return the number of published monster waves."""
        return len(self.monster_list)

class InfiniteWave(NanokaModel):
    """A PF infinite-wave definition with monster groups, spawn limits, and modifiers.

    Keep the elite-group and ability parameter references used for wave HP and
    mechanics calculations; this model performs no calculations or asset loading.
    """
    infinite_wave_id: int | None = None
    monster_group_id_list: list[int] = Field(default_factory=list)
    max_monster_count: int | None = None
    max_teammate_count: int | None = None
    ability: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    elite_group: int | None = None

class BossConfigTag(NanokaModel):
    """A boss mechanic tag with text, parameters, skill reference, and nested tags."""
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    param: list[float | int] = Field(default_factory=list)
    param_fix: list[float | int] = Field(default_factory=list)
    skill_id: int | None = None
    child: list["BossConfigTag"] = Field(default_factory=list)

class BossPhase(NanokaModel):
    """A boss phase description with response hints, difficulty, and referenced skills."""
    name: str | None = None
    desc: str | None = None
    answer: str | None = None
    difficulty: int | None = None
    skill_list: list[int] = Field(default_factory=list)

class BossConfig(NanokaModel):
    """Boss difficulty choices, mechanic tags, guides, and phase descriptions.

    Collections remain in provider order so renderers can present all published
    mechanics without fetching or selecting a season.
    """
    difficulty: int | None = None
    difficulty_list: list[int] = Field(default_factory=list)
    tag_list: list[BossConfigTag] = Field(default_factory=list)
    difficulty_guide_list: list[BossConfigTag] = Field(default_factory=list)
    text_guide_list: list[str] = Field(default_factory=list)
    phase_list: list[BossPhase] = Field(default_factory=list)

class StageChallenge(NanokaModel):
    """A score/objective condition with scalar or list-shaped description parameters.

    params accepts either param representation and falls back to param_list.
    """
    name: str | None = None
    desc: str | None = None
    param: float | int | list[float | int] | None = None
    param_list: list[float | int] = Field(default_factory=list)

    @computed_field
    @property
    def params(self) -> list[float | int]:
        """Return list/scalar parameters, falling back to the published param_list."""
        if isinstance(self.param, list):
            return self.param
        if self.param is not None:
            return list(self.param_list or [self.param])
        return list(self.param_list)

class StageLevel(NanokaModel):
    """One endgame floor or continuation record with challenges and combat nodes.

    Retain base and numbered node fields for bosses, events, infinite waves, NPC
    monsters, recommended elements, and mechanics. Continuation IDs are data;
    services decide how records compose into a rendered floor.
    """
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
        """Return unique IDs referenced by boss definitions in encounter order."""
        found = [
            value
            for value in (self.boss_monster_id, self.boss_monster_id1, self.boss_monster_id2)
            if value is not None
        ]
        return list(dict.fromkeys(found))

    @computed_field
    @property
    def events(self) -> list[StageEvent]:
        """Return the published stage events in provider order."""
        events = list(self.event_id_list)
        events.extend(self.event_id_list1)
        events.extend(self.event_id_list2)
        return events

    @computed_field
    @property
    def all_events(self) -> list[StageEvent]:
        """Return the same stage event list exposed by events."""
        return self.events

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        """Return unique referenced monster IDs in encounter order."""
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
        """Return unique monster IDs, including nested wave/invasion references."""
        return self.monster_ids

    @computed_field
    @property
    def infinite_waves(self) -> list[InfiniteWave]:
        """Return all infinite-mode waves published in this stage."""
        waves: list[InfiniteWave] = []
        for mapping in (self.infinite_list, self.infinite_list1, self.infinite_list2):
            waves.extend(mapping.values())
        return waves

    @computed_field
    @property
    def elements(self) -> list[str]:
        """Return unique recommended elements in lowercase and encounter order."""
        found = list(self.damage_type) + list(self.damage_type1) + list(self.damage_type2)
        return list(dict.fromkeys(value.lower() for value in found if value))

    @field_validator("challenge", "challenge_special", mode="before")
    @classmethod
    def _accept_challenge_dict(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return [value]
        return value

class EndgameDetail(NanokaModel):
    """A MOC/PF/AS season document with floors, buffs, options, and optional date bounds.

    mode records the canonical provider mode. Stage and boss helpers expose parsed
    data; live status requires both valid UTC detail dates.
    """
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
        """Return stage models in published encounter order."""
        return self.level

    @computed_field
    @property
    def boss_stage(self) -> StageLevel | None:
        """Return the last nonempty stage, or None when no boss stage exists."""
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
        """Return unique boss IDs for the designated boss stage, or [] if unavailable."""
        stage = self.boss_stage
        return stage.boss_ids if stage else []

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        """Return unique referenced monster IDs in encounter order."""
        found: list[int] = []
        for stage in self.level:
            found.extend(stage.monster_ids)
        return list(dict.fromkeys(found))

    @computed_field
    @property
    def starts_at(self) -> datetime | None:
        """Return the published detail start time as UTC, or None if absent/invalid."""
        return parse_datetime(self.begin_time)

    @computed_field
    @property
    def ends_at(self) -> datetime | None:
        """Return the published detail end time as UTC, or None if absent/invalid."""
        return parse_datetime(self.end_time)

    @computed_field
    @property
    def is_live(self) -> bool:
        """Return whether the current UTC time lies within both published date boundaries."""
        start, end = self.starts_at, self.ends_at
        return bool(start and end and start <= as_utc() <= end)

    @field_validator("level", mode="before")
    @classmethod
    def _accept_stage_dict(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return [value]
        return value

class PeakBossLevel(StageLevel):
    """The AA boss-stage specialization of the shared endgame stage model."""
    pass

class PeakDetail(NanokaModel):
    """An AA document containing preparation stages, boss stage, and boss mechanics.

    No dependable live date window is inferred. This model exposes published data
    without enabling deferred AA floor-card rendering.
    """
    id: int | None = None
    name: str | None = None
    pre_level: list[StageLevel] = Field(default_factory=list)
    boss_level: StageLevel | None = None
    boss_config: BossConfig | None = None
    mode: str | None = None

    @computed_field
    @property
    def stages(self) -> list[StageLevel]:
        """Return preparation stages followed by the optional peak boss stage."""
        return [*self.pre_level, *([self.boss_level] if self.boss_level else [])]

    @computed_field
    @property
    def boss_stage(self) -> StageLevel | None:
        """Return the explicit peak boss stage, or None when absent."""
        return self.boss_level

    @computed_field
    @property
    def boss_ids(self) -> list[int]:
        """Return unique boss IDs for the designated boss stage, or [] if unavailable."""
        return self.boss_level.boss_ids if self.boss_level else []

    @computed_field
    @property
    def boss_name(self) -> str | None:
        """Return the designated boss-stage name, falling back to the peak name."""
        return self.boss_level.name if self.boss_level else self.name

    @computed_field
    @property
    def monster_ids(self) -> list[int]:
        """Return unique referenced monster IDs in encounter order."""
        found: list[int] = list(self.boss_ids)
        for stage in self.pre_level:
            found.extend(stage.monster_ids)
        if self.boss_level:
            found.extend(self.boss_level.monster_ids)
        return list(dict.fromkeys(found))

__all__ = ['StageConfigValue', 'MonsterSlot', 'StageInvasion', 'StageMonster', 'StageEvent', 'InfiniteWave', 'BossConfigTag', 'BossPhase', 'BossConfig', 'StageChallenge', 'StageLevel', 'EndgameDetail', 'PeakBossLevel', 'PeakDetail']
