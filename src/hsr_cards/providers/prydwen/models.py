"""Stable, reviewable schema for one Prydwen character build.

The models deliberately keep Prydwen's editorial wording. They normalize shape
(weights, ordering, references) but never paraphrase a recommendation.

The JSON file is the review artifact and the input to card rendering. It is not
automatically trusted: ``review.status`` separates "draft" parses from builds
that a human has explicitly approved. Card-facing extras (icons, trace bonuses,
investment guidance) are stored here too so the renderer never needs the web.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    """Reject unknown source fields and trim strings while validating domain data."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AssetRef(StrictModel):
    """A reusable Nanoka asset reference, not a Prydwen CDN URL.

    ``ref`` is the stable SDK key (``character:1415``, ``lightcone:23037``,
    ``relic:122``, ``element:ice``, ``path:erudition``, ``skill:1401:Normal``,
    ``stat:CriticalChance``). ``relative_path`` is the path below Nanoka's
    ``assets/hsr/`` root and is what cards use to load the cached local file.
    The source URL is retained only for review.
    """

    ref: str
    relative_path: str
    local_name: str
    source_url: HttpUrl | None = None


class ReviewStatus(str, Enum):
    """Distinguish an unreviewed draft from an explicitly approved build."""
    DRAFT = "draft"
    APPROVED = "approved"


class ReviewInfo(StrictModel):
    """Record approval status, reviewer identity, timestamp, and optional review notes."""
    status: ReviewStatus = ReviewStatus.DRAFT
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    note: str | None = None


class CharacterIdentity(StrictModel):
    """Preserve source character identity, publication metadata, and resolved artwork references."""
    name: str
    slug: str
    title: str | None = None
    rarity: int | None = Field(default=None, ge=1, le=5)
    element: str
    path: str
    version: str | None = None
    last_updated: str | None = None
    description: str | None = None
    source_url: HttpUrl
    nanoka_id: int | None = None
    icon: AssetRef | None = None
    round_icon: AssetRef | None = None
    drawcard: AssetRef | None = None
    element_icon: AssetRef | None = None
    path_icon: AssetRef | None = None


class CharacterStats(StrictModel):
    """Store source base HP, attack, defence, and speed; unavailable values remain None."""
    hp: int | None = None
    atk: int | None = None
    defence: int | None = None
    speed: int | None = None


class WeightClass(str, Enum):
    """Preserve source recommendation categories without converting them into numerical scores."""
    BEST = "best"
    ALTERNATIVE = "alternative"
    GENERAL = "general"
    SPECIFIC = "specific"
    SPECIALIST = "specialist"


class LightConeRecommendation(StrictModel):
    """Store one ranked cone with superimposition, source conditions, and a local asset reference."""
    name: str
    heading: str | None = None
    build_type: str | None = None
    superimposition: int | None = Field(default=None, ge=1, le=5)
    rarity: int | None = Field(default=None, ge=1, le=5)
    rank: int | None = Field(default=None, ge=1)
    score: float | None = None
    score_text: str | None = None
    weight: WeightClass = WeightClass.ALTERNATIVE
    reason: str | None = None
    usage: str | None = None
    endgame_notes: dict[str, str] = Field(default_factory=dict)
    asset: AssetRef | None = None


class RelicRecommendation(StrictModel):
    """Store one relic option, retaining piece counts and two-piece combination membership."""
    name: str
    pieces: int | None = Field(default=None, ge=2, le=4)
    rank: int | None = Field(default=None, ge=1)
    combination_id: str | None = None
    slot: Literal["cavern", "planar"] = "cavern"
    score: float | None = None
    score_text: str | None = None
    weight: WeightClass = WeightClass.ALTERNATIVE
    reason: str | None = None
    usage: str | None = None
    flex: bool = False
    asset: AssetRef | None = None


class RelicWeightGroup(StrictModel):
    """Group cavern or planar recommendations beneath their original source heading."""
    heading: str
    weight: WeightClass
    slot: Literal["cavern", "planar"] = "cavern"
    recommendations: list[RelicRecommendation] = Field(default_factory=list)


class StatChoice(StrictModel):
    """Keep ordered stat alternatives, comparison operators, and source wording for one relic slot."""
    slot: str
    values: list[str] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    raw_text: str
    icons: list[AssetRef | None] = Field(default_factory=list)


class StatTarget(StrictModel):
    """Keep a recommended stat threshold and the exact conditions that qualify it."""
    stat: str
    target: str
    notes: list[str] = Field(default_factory=list)
    icon: AssetRef | None = None


class TracePriority(StrictModel):
    """Retain source skill/major-trace priorities, operators, and resolved step icons."""
    skills: str | None = None
    major_traces: str | None = None
    raw_text: str | None = None
    skill_steps: list["TraceStep"] = Field(default_factory=list)
    skill_operators: list[str] = Field(default_factory=list)


class TraceBonus(StrictModel):
    """Store one minor-trace stat increase with its source value and optional icon."""
    stat: str
    value: str
    icon: AssetRef | None = None


class TraceStep(StrictModel):
    """Store a source priority label and an optional resolved combat-skill icon."""
    label: str
    asset: AssetRef | None = None


class SkillInfo(StrictModel):
    """One combat skill or major trace shown in the kit section."""

    kind: str
    name: str
    trace_level: str | None = None
    description: str | None = None
    icon: AssetRef | None = None


class InvestmentOption(StrictModel):
    """Preserve one investment priority and its qualifying source note."""
    label: str
    note: str | None = None


class InvestmentGuide(StrictModel):
    """Preserve ordered investment recommendations and general investment notes."""
    order: list[InvestmentOption] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Synergy(StrictModel):
    """One editorial synergy entry from the build tab.

    ``characters`` may contain several linked characters for grouped entries
    such as the Aventurine/Lingsha sustain pair.
    """

    characters: list[str] = Field(default_factory=list)
    character_assets: list[AssetRef | None] = Field(default_factory=list)
    note: str
    role: str | None = None
    snippet: str | None = None


class TeamVariant(StrictModel):
    """Keep one analytics team with usage, performance metrics, and character identities."""
    characters: list[str] = Field(default_factory=list)
    character_assets: list[AssetRef | None] = Field(default_factory=list)
    rank: int | None = None
    application_rate: str | None = None
    performance: dict[str, str] = Field(default_factory=dict)
    raw_metrics: dict[str, float | int | None] = Field(default_factory=dict)
    character_slugs: list[str] = Field(default_factory=list)


class EditorTeamMember(StrictModel):
    """Store one editorial member choice with its slot, role, and optional artwork."""
    name: str
    slot: int | None = None
    role: str | None = None
    asset: AssetRef | None = None


class EditorTeamSlot(StrictModel):
    """Group alternatives for one team slot without increasing the party size."""
    role: str | None = None
    members: list[EditorTeamMember] = Field(default_factory=list)


class EditorTeam(StrictModel):
    """Keep one source editorial team, including slot alternatives and explanatory notes."""
    name: str
    members: list[EditorTeamMember] = Field(default_factory=list)
    slots: list[EditorTeamSlot] = Field(default_factory=list)
    note: str | None = None


class TeamMode(StrictModel):
    """Group analytics teams under their actual game mode and source snapshot or phase."""
    mode: str
    label: str
    variants: list[TeamVariant] = Field(default_factory=list)
    source_file: str | None = None
    source_path: str | None = None
    phase: str | None = None


class SourceMeta(StrictModel):
    """Revision metadata shown on the card and used for review diffs."""

    url: str
    fetched_at: datetime | None = None
    last_updated: str | None = None
    last_review_update: str | None = None
    last_major_build_update: str | None = None
    primary_mode: str | None = None
    html_sha256: str | None = None
    raw_file: str | None = None
    parser_version: str = "2"
    website_updates: dict[str, str] = Field(default_factory=dict)


class BuildCardData(StrictModel):
    """Validated build input preserving source conditions, review state, diagnostics, and render data."""
    schema_version: Literal[1] = 1
    generated_at: datetime
    source: str
    source_meta: SourceMeta | None = None
    review: ReviewInfo = Field(default_factory=ReviewInfo)
    character: CharacterIdentity
    build_name: str | None = None
    stats: CharacterStats = Field(default_factory=CharacterStats)
    light_cones: list[LightConeRecommendation] = Field(default_factory=list)
    relic_sets: list[RelicWeightGroup] = Field(default_factory=list)
    mixed_relic_sets: list[AssetRef] = Field(default_factory=list)
    main_stats: list[StatChoice] = Field(default_factory=list)
    substats: list[str] = Field(default_factory=list)
    substats_raw: str | None = None
    stat_targets: list[StatTarget] = Field(default_factory=list)
    stat_target_notes: list[str] = Field(default_factory=list)
    trace_priority: TracePriority = Field(default_factory=TracePriority)
    trace_bonuses: list[TraceBonus] = Field(default_factory=list)
    skills: list[SkillInfo] = Field(default_factory=list)
    major_traces: list[SkillInfo] = Field(default_factory=list)
    investment: InvestmentGuide = Field(default_factory=InvestmentGuide)
    review_notes: list[str] = Field(default_factory=list)
    editorial_teams: list[EditorTeam] = Field(default_factory=list)
    synergies: list[Synergy] = Field(default_factory=list)
    synergy_intro: str | None = None
    teams: list[TeamMode] = Field(default_factory=list)
    team_comments: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, bool] = Field(default_factory=dict)

    @field_validator("source")
    @classmethod
    def source_is_reviewable(cls, value: str) -> str:
        """Reject blank source identifiers with ValueError before accepting a build."""
        if not value.strip():
            raise ValueError("source must identify the extracted page")
        return value

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible build payload, retaining explicit null fields."""
        return self.model_dump(mode="json", exclude_none=False)


class TeamIndex(StrictModel):
    """Store a generated cross-character team index and the draft entries omitted from it."""
    schema_version: Literal[1] = 1
    generated_at: datetime
    review: ReviewInfo = Field(default_factory=ReviewInfo)
    characters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    skipped: list[dict[str, str]] = Field(default_factory=list)

TIER_LIST_URL = "https://www.prydwen.gg/star-rail/tier-list"
GameMode = Literal["MOC", "PF", "AS"]

@dataclass(frozen=True, slots=True)
class Reward:
    """One reward granted by a redeem code."""

    name: str
    count: int
    url: str


@dataclass(frozen=True, slots=True)
class RedeemCode:
    """One active redeem code and all rewards it grants."""

    code: str
    redeem_url: str 
    rewards: list[Reward]


@dataclass(frozen=True, slots=True)
class RoleHeader:
    """Identify one tier-list role column and its display name."""
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class TierCharacter:
    """Store a tier-listed character with portrait, form, tags, and rating-change marks."""
    name: str
    slug: str
    icon_url: str
    element: str
    rarity: int
    eidolon: str
    tags: list[str]
    marks: list[str]

    @property
    def url(self) -> str:
        """Return the public Prydwen character URL for this source slug."""
        return f"https://www.prydwen.gg/star-rail/characters/{self.slug}"


@dataclass(frozen=True, slots=True)
class TierRole:
    """Group characters sharing one role within a tier."""
    key: str
    name: str
    characters: list[TierCharacter]


@dataclass(frozen=True, slots=True)
class Tier:
    """Group the role columns for one named source tier."""
    name: str
    key: str
    roles: list[TierRole]


@dataclass(frozen=True, slots=True)
class TierGroup:
    """Group tiers under the source apex, meta, niche, or forgotten heading."""
    key: str
    name: str
    tiers: list[Tier]


@dataclass(frozen=True, slots=True)
class TierListData:
    """Store one mode-specific tier list with update metadata, role headers, and source URL."""
    mode: str
    mode_key: str
    updated: str | None
    roles: list[RoleHeader]
    groups: list[TierGroup]
    source: str = TIER_LIST_URL

    @property
    def tiers(self) -> list[Tier]:
        """Return tiers in source group order as a flattened list."""
        return [tier for group in self.groups for tier in group.tiers]

