"""Tolerant character summaries, skills, traces, stats, and build models."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import Field, computed_field
from ..locales import DEFAULT_LOCALE, Locale

from .common import MaterialCost, NanokaModel, localized_field, normalize_path, normalize_path_codename, parse_rarity, sum_optional, unix_datetime

class CharacterSummary(NanokaModel):
    """A catalog character identity with multilingual names and release metadata.

    Numeric id is required; an absent release timestamp denotes a beta entry.
    Path/element fields accept the provider baseType/damageType aliases.
    """
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
        """Return the English display name with other-language fallback, or None."""
        return localized_field(self, "en", "en", "zh", "ja", "ko")

    @computed_field
    @property
    def stars(self) -> int | None:
        """Return numeric rarity stars, or None when the provider rarity is unknown."""
        return parse_rarity(self.rank)

    @computed_field
    @property
    def path(self) -> str | None:
        """Return the normalized display path, or None when no path is supplied."""
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        """Return the normalized provider path codename, or None if absent."""
        return normalize_path_codename(self.base_type)

    @computed_field
    @property
    def element(self) -> str | None:
        """Return the lowercase damage element, or None if absent."""
        return (self.damage_type or "").lower() or None

    @computed_field
    @property
    def released(self) -> bool:
        """Return whether a release timestamp is published."""
        return self.release is not None

    @computed_field
    @property
    def is_beta(self) -> bool:
        """Return whether the entry has no published release timestamp."""
        return self.release is None

    @computed_field
    @property
    def release_datetime(self) -> datetime | None:
        """Return the published Unix release timestamp as UTC, or None."""
        return unix_datetime(self.release)

    def display_name(
        self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True
    ) -> str | None:
        """Return the requested locale name with optional en/zh/ja/ko fallback.

        Locale aliases are accepted. Return None if absent; invalid aliases raise
        ValueError. Game ruby markup is removed without performing IO.
        """
        return localized_field(self, locale, "en", "zh", "ja", "ko", fallback=fallback)

    @classmethod
    def from_entry(cls, identifier: str | int, payload: dict[str, Any]) -> "CharacterSummary":
        """Parse a provider catalog entry with a numeric identifier into this model.

        Unknown fields are retained;
        invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.
        """
        return cls.model_validate({"id": int(identifier), **payload})

class CharacterRank(NanokaModel):
    """An eidolon or additional-rank effect with its text, icon, and parameters.

    Numeric id identifies the rank; optional metadata and unknown fields are
    retained without resolving or downloading the icon.
    """
    id: int
    name: str | None = None
    desc: str | None = None
    icon: str | None = None
    param_list: list[float | int] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

class SkillLevel(NanokaModel):
    """One published character skill level and its description parameter array."""
    level: int | None = None
    param_list: list[float | int] = Field(default_factory=list)

class SkillExtra(NanokaModel):
    """An additional skill text block with alternate param/param_list payloads."""
    name: str | None = None
    desc: str | None = None
    param: list[float | int] = Field(default_factory=list)
    param_list: list[float | int] = Field(default_factory=list)

class CharacterSkill(NanokaModel):
    """A character skill with combat costs, type labels, extras, and level parameters.

    Numeric id is required. Level entries remain keyed by provider strings;
    missing type labels can denote an enhanced or split skill variant.
    """
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
        """Return the published parameter array for numeric skill level, or None if absent."""
        entry = self.level.get(str(level))
        return entry.param_list if entry else None

    @computed_field
    @property
    def max_level(self) -> int | None:
        """Return the highest numeric skill level, or None if no levels exist."""
        levels = [int(key) for key in self.level if str(key).isdigit()]
        return max(levels) if levels else None

    @computed_field
    @property
    def is_attack(self) -> bool:
        """Return whether the skill belongs to a standard combat/technique type."""
        return self.type in {"Normal", "BPSkill", "Ultra", "Maze", "Talent"}

class SkillTreeLevel(NanokaModel):
    """One trace level with unlock requirements, costs, bonuses, and display metadata.

    Retain both legacy textual and newer numeric point-trigger keys. Missing
    optional fields stay absent instead of inventing unlock or stat requirements.
    """
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
    """Trace levels grouped under one provider point identifier.

    The first defined level metadata supplies its display text, icon, and point
    type; point types distinguish minor traces, major traces, and bonus abilities.
    """
    point: str
    levels: list[SkillTreeLevel] = Field(default_factory=list)

    @computed_field
    @property
    def point_type(self) -> int | None:
        """Return the first defined trace point type, or None if every level omits it."""
        return next((level.point_type for level in self.levels if level.point_type is not None), None)

    @computed_field
    @property
    def is_bonus_ability(self) -> bool:
        """Return whether the trace point type denotes a bonus ability (3)."""
        return self.point_type == 3

    @computed_field
    @property
    def is_major_trace(self) -> bool:
        """Return whether the trace point type denotes a major trace (2)."""
        return self.point_type == 2

    @computed_field
    @property
    def is_minor_trace(self) -> bool:
        """Return whether the trace point type denotes a minor trace (1)."""
        return self.point_type == 1

    @computed_field
    @property
    def name(self) -> str | None:
        """Return the first published trace-level name, or None."""
        return next((level.point_name for level in self.levels if level.point_name), None)

    @computed_field
    @property
    def description(self) -> str | None:
        """Return the first published trace-level description, or None."""
        return next((level.point_desc for level in self.levels if level.point_desc), None)

    @computed_field
    @property
    def icon(self) -> str | None:
        """Return the first published trace-level icon, or None when absent."""
        return next((level.icon for level in self.levels if level.icon), None)

class VoiceActors(NanokaModel):
    """Optional Chinese, Japanese, Korean, and English voice-actor credits."""
    chinese: str | None = None
    japanese: str | None = None
    korean: str | None = None
    english: str | None = None

class CharacterInfo(NanokaModel):
    """Character faction, voice actors, stories, and published voice-line metadata."""
    camp: str | None = None
    va: VoiceActors = Field(default_factory=VoiceActors)
    stories: dict[str, str | None] = Field(default_factory=dict)
    voicelines: list[dict[str, Any]] = Field(default_factory=list)

class CharacterStat(NanokaModel):
    """Base and additive character stats, promotion metadata, and material costs.

    Computed ATK/DEF/HP add available components and retain None when both are
    missing; this model does not apply equipment or combat buffs.
    """
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
        """Return base plus additive ATK, retaining None when both values are absent."""
        return sum_optional(self.attack_base, self.attack_add)

    @computed_field
    @property
    def defence(self) -> float | None:
        """Return base plus additive DEF, retaining None when both values are absent."""
        return sum_optional(self.defence_base, self.defence_add)

    @computed_field
    @property
    def hp(self) -> float | None:
        """Return base plus additive HP, retaining None when both values are absent."""
        return sum_optional(self.hp_base, self.hp_add)

class CharacterRelicBuild(NanokaModel):
    """Provider relic/planar recommendations, main stats, and preferred substats.

    Keep the ordered set-ID recommendations and provider property groups;
    helpers expose the first recommended sets and slot-specific main-stat data.
    """
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
        """Return main-stat recommendations grouped by relic slot; omitted slots stay absent."""
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
        """Return the first four-piece relic recommendation ID, or None if unavailable."""
        return self.set4_id_list[0] if self.set4_id_list else None

    @computed_field
    @property
    def planar_set(self) -> int | None:
        """Return the first two-piece planar recommendation ID, or None if unavailable."""
        return self.set2_id_list[0] if self.set2_id_list else None

class CharacterTeam(NanokaModel):
    """A recommended leading avatar, ordered team members, and backup groups.

    The members accessor combines the leading avatar with member_list without
    resolving IDs into character objects.
    """
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
        """Return the leading avatar and other team members, preserving their order."""
        return [self.avatar_id, *self.member_list] if self.avatar_id else list(self.member_list)

class CharacterDetail(NanokaModel):
    """A complete character document containing skills, traces, ranks, stats, and builds.

    Nested mappings preserve provider IDs and unknown fields. Optional memosprite,
    enhanced-skill, lore, equipment, team, and skin data remain available as published.
    """
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
        """Return numeric rarity stars, or None when the provider rarity is unknown."""
        return parse_rarity(self.rarity)

    @computed_field
    @property
    def path(self) -> str | None:
        """Return the normalized display path, or None when no path is supplied."""
        return normalize_path(self.base_type)

    @computed_field
    @property
    def path_codename(self) -> str | None:
        """Return the normalized provider path codename, or None if absent."""
        return normalize_path_codename(self.base_type)

    @computed_field
    @property
    def element(self) -> str | None:
        """Return the lowercase damage element, or None if absent."""
        return (self.damage_type or "").lower() or None

    @computed_field
    @property
    def eidolons(self) -> list[CharacterRank]:
        """Return eidolon models sorted by numeric rank ID."""
        return sorted(
            self.ranks.values(),
            key=lambda rank: int(rank.id) if str(rank.id).isdigit() else 0,
        )

    @computed_field
    @property
    def extra_ranks(self) -> list[CharacterRank]:
        """Return additional rank models sorted by ID."""
        return sorted(self.ex_ranks.values(), key=lambda rank: rank.id)

    @computed_field
    @property
    def traces(self) -> list[CharacterTrace]:
        """Return grouped trace-level models in provider point order."""
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
        """Return traces whose provider point type is bonus ability (3)."""
        return [trace for trace in self.traces if trace.is_bonus_ability]

    @computed_field
    @property
    def major_traces(self) -> list[CharacterTrace]:
        """Return traces whose provider point type is major trace (2)."""
        return [trace for trace in self.traces if trace.is_major_trace]

    @computed_field
    @property
    def minor_traces(self) -> list[CharacterTrace]:
        """Return traces whose provider point type is minor trace (1)."""
        return [trace for trace in self.traces if trace.is_minor_trace]

    @computed_field
    @property
    def max_stat(self) -> CharacterStat | None:
        """Return the highest numeric promotion stat block, or None if no stats exist."""
        if not self.stats:
            return None
        key = max(self.stats, key=lambda value: int(value) if str(value).isdigit() else -1)
        return self.stats[key]

    @computed_field
    @property
    def basic_attack(self) -> CharacterSkill | None:
        """Return the first Normal skill, or None if absent."""
        return next(
            (skill for skill in self.skills.values() if skill.type == "Normal"),
            None,
        )

    @computed_field
    @property
    def skill(self) -> CharacterSkill | None:
        """Return the first BPSkill entry, or None if absent."""
        return next(
            (skill for skill in self.skills.values() if skill.type == "BPSkill"),
            None,
        )

    @computed_field
    @property
    def ultimate(self) -> CharacterSkill | None:
        """Return the first Ultra skill, or None if absent."""
        return next(
            (skill for skill in self.skills.values() if skill.type == "Ultra"),
            None,
        )

    @computed_field
    @property
    def talent(self) -> CharacterSkill | None:
        """Return the first skill labeled Talent, or None if absent."""
        return next(
            (skill for skill in self.skills.values() if skill.type_name == "Talent"),
            None,
        )

    @computed_field
    @property
    def technique(self) -> CharacterSkill | None:
        """Return the first Maze skill, or None if absent."""
        return next(
            (skill for skill in self.skills.values() if skill.type == "Maze"),
            None,
        )

    @computed_field
    @property
    def enhanced_skills(self) -> list[CharacterSkill]:
        """Return unlabeled skill entries used for enhanced or split skill variants."""
        return [
            skill
            for skill in self.skills.values()
            if skill.type is None and skill.type_name is None
        ]

__all__ = ['CharacterSummary', 'CharacterRank', 'SkillLevel', 'SkillExtra', 'CharacterSkill', 'SkillTreeLevel', 'CharacterTrace', 'VoiceActors', 'CharacterInfo', 'CharacterStat', 'CharacterRelicBuild', 'CharacterTeam', 'CharacterDetail']
