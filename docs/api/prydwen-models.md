# Prydwen models

Field names and defaults below reflect the repository code. `Required` means the provider/model constructor must supply that field; optional fields show their default. Pydantic models support `model_validate(payload)`, `model_dump()`, and `model_dump_json()`. Use `model_dump(mode="json")` for JSON-compatible values; dataclasses instead expose their typed attributes directly.

Import build schemas from `hsr_cards.providers.prydwen.models`; compatibility build imports remain under `hsr_cards.prydwen.builds.models`. `RedeemCode`, `Reward`, and `TierListData` are also available directly from `hsr_cards`.

`TierListData` uses `.mode` and `.mode_key` for the selected game mode, `.groups` for source grouping, and `.tiers` for a flattened view. Build models preserve review status and source conditions; approval/rendering workflows are in the [build guide](../guides/builds.md).

## Build schemas

### `StrictModel`

Reject unknown source fields and trim strings while validating domain data.

### `AssetRef`

A reusable Nanoka asset reference, not a Prydwen CDN URL.

``ref`` is the stable SDK key (``character:1415``, ``lightcone:23037``,
``relic:122``, ``element:ice``, ``path:erudition``, ``skill:1401:Normal``,
``stat:CriticalChance``). ``relative_path`` is the path below Nanoka's
``assets/hsr/`` root and is what cards use to load the cached local file.
The source URL is retained only for review.

Fields:

- `ref: str`: Required.
- `relative_path: str`: Required.
- `local_name: str`: Required.
- `source_url: pydantic.networks.HttpUrl | None`: Default: `None`.

### `ReviewInfo`

Record approval status, reviewer identity, timestamp, and optional review notes.

Fields:

- `status: ReviewStatus`: Default: `ReviewStatus.DRAFT`.
- `reviewer: str | None`: Default: `None`.
- `reviewed_at: datetime | None`: Default: `None`.
- `note: str | None`: Default: `None`.

### `CharacterIdentity`

Preserve source character identity, publication metadata, and resolved artwork references.

Fields:

- `name: str`: Required.
- `slug: str`: Required.
- `title: str | None`: Default: `None`.
- `rarity: int | None`: Default: `None`.
- `element: str`: Required.
- `path: str`: Required.
- `version: str | None`: Default: `None`.
- `last_updated: str | None`: Default: `None`.
- `description: str | None`: Default: `None`.
- `source_url: pydantic.networks.HttpUrl`: Required.
- `nanoka_id: int | None`: Default: `None`.
- `icon: AssetRef | None`: Default: `None`.
- `round_icon: AssetRef | None`: Default: `None`.
- `drawcard: AssetRef | None`: Default: `None`.
- `element_icon: AssetRef | None`: Default: `None`.
- `path_icon: AssetRef | None`: Default: `None`.

### `CharacterStats`

Store source base HP, attack, defence, and speed; unavailable values remain None.

Fields:

- `hp: int | None`: Default: `None`.
- `atk: int | None`: Default: `None`.
- `defence: int | None`: Default: `None`.
- `speed: int | None`: Default: `None`.

### `LightConeRecommendation`

Store one ranked cone with superimposition, source conditions, and a local asset reference.

Fields:

- `name: str`: Required.
- `heading: str | None`: Default: `None`.
- `build_type: str | None`: Default: `None`.
- `superimposition: int | None`: Default: `None`.
- `rarity: int | None`: Default: `None`.
- `rank: int | None`: Default: `None`.
- `score: float | None`: Default: `None`.
- `score_text: str | None`: Default: `None`.
- `weight: WeightClass`: Default: `WeightClass.ALTERNATIVE`.
- `reason: str | None`: Default: `None`.
- `usage: str | None`: Default: `None`.
- `endgame_notes: dict[str, str]`: Default: `{}`.
- `asset: AssetRef | None`: Default: `None`.

### `RelicRecommendation`

Store one relic option, retaining piece counts and two-piece combination membership.

Fields:

- `name: str`: Required.
- `pieces: int | None`: Default: `None`.
- `rank: int | None`: Default: `None`.
- `combination_id: str | None`: Default: `None`.
- `slot: Literal['cavern', 'planar']`: Default: `'cavern'`.
- `score: float | None`: Default: `None`.
- `score_text: str | None`: Default: `None`.
- `weight: WeightClass`: Default: `WeightClass.ALTERNATIVE`.
- `reason: str | None`: Default: `None`.
- `usage: str | None`: Default: `None`.
- `flex: bool`: Default: `False`.
- `asset: AssetRef | None`: Default: `None`.

### `RelicWeightGroup`

Group cavern or planar recommendations beneath their original source heading.

Fields:

- `heading: str`: Required.
- `weight: WeightClass`: Required.
- `slot: Literal['cavern', 'planar']`: Default: `'cavern'`.
- `recommendations: list[RelicRecommendation]`: Default: `[]`.

### `StatChoice`

Keep ordered stat alternatives, comparison operators, and source wording for one relic slot.

Fields:

- `slot: str`: Required.
- `values: list[str]`: Default: `[]`.
- `operators: list[str]`: Default: `[]`.
- `raw_text: str`: Required.
- `icons: list[AssetRef | None]`: Default: `[]`.

### `StatTarget`

Keep a recommended stat threshold and the exact conditions that qualify it.

Fields:

- `stat: str`: Required.
- `target: str`: Required.
- `notes: list[str]`: Default: `[]`.
- `icon: AssetRef | None`: Default: `None`.

### `TracePriority`

Retain source skill/major-trace priorities, operators, and resolved step icons.

Fields:

- `skills: str | None`: Default: `None`.
- `major_traces: str | None`: Default: `None`.
- `raw_text: str | None`: Default: `None`.
- `skill_steps: ForwardRef("list['TraceStep']")`: Default: `[]`.
- `skill_operators: list[str]`: Default: `[]`.

### `TraceBonus`

Store one minor-trace stat increase with its source value and optional icon.

Fields:

- `stat: str`: Required.
- `value: str`: Required.
- `icon: AssetRef | None`: Default: `None`.

### `TraceStep`

Store a source priority label and an optional resolved combat-skill icon.

Fields:

- `label: str`: Required.
- `asset: AssetRef | None`: Default: `None`.

### `SkillInfo`

One combat skill or major trace shown in the kit section.

Fields:

- `kind: str`: Required.
- `name: str`: Required.
- `trace_level: str | None`: Default: `None`.
- `description: str | None`: Default: `None`.
- `icon: AssetRef | None`: Default: `None`.

### `InvestmentOption`

Preserve one investment priority and its qualifying source note.

Fields:

- `label: str`: Required.
- `note: str | None`: Default: `None`.

### `InvestmentGuide`

Preserve ordered investment recommendations and general investment notes.

Fields:

- `order: list[InvestmentOption]`: Default: `[]`.
- `notes: list[str]`: Default: `[]`.

### `Synergy`

One editorial synergy entry from the build tab.

``characters`` may contain several linked characters for grouped entries
such as the Aventurine/Lingsha sustain pair.

Fields:

- `characters: list[str]`: Default: `[]`.
- `character_assets: list[AssetRef | None]`: Default: `[]`.
- `note: str`: Required.
- `role: str | None`: Default: `None`.
- `snippet: str | None`: Default: `None`.

### `TeamVariant`

Keep one analytics team with usage, performance metrics, and character identities.

Fields:

- `characters: list[str]`: Default: `[]`.
- `character_assets: list[AssetRef | None]`: Default: `[]`.
- `rank: int | None`: Default: `None`.
- `application_rate: str | None`: Default: `None`.
- `performance: dict[str, str]`: Default: `{}`.
- `raw_metrics: dict[str, float | int | None]`: Default: `{}`.
- `character_slugs: list[str]`: Default: `[]`.

### `EditorTeamMember`

Store one editorial member choice with its slot, role, and optional artwork.

Fields:

- `name: str`: Required.
- `slot: int | None`: Default: `None`.
- `role: str | None`: Default: `None`.
- `asset: AssetRef | None`: Default: `None`.

### `EditorTeamSlot`

Group alternatives for one team slot without increasing the party size.

Fields:

- `role: str | None`: Default: `None`.
- `members: list[EditorTeamMember]`: Default: `[]`.

### `EditorTeam`

Keep one source editorial team, including slot alternatives and explanatory notes.

Fields:

- `name: str`: Required.
- `members: list[EditorTeamMember]`: Default: `[]`.
- `slots: list[EditorTeamSlot]`: Default: `[]`.
- `note: str | None`: Default: `None`.

### `TeamMode`

Group analytics teams under their actual game mode and source snapshot or phase.

Fields:

- `mode: str`: Required.
- `label: str`: Required.
- `variants: list[TeamVariant]`: Default: `[]`.
- `source_file: str | None`: Default: `None`.
- `source_path: str | None`: Default: `None`.
- `phase: str | None`: Default: `None`.

### `SourceMeta`

Revision metadata shown on the card and used for review diffs.

Fields:

- `url: str`: Required.
- `fetched_at: datetime | None`: Default: `None`.
- `last_updated: str | None`: Default: `None`.
- `last_review_update: str | None`: Default: `None`.
- `last_major_build_update: str | None`: Default: `None`.
- `primary_mode: str | None`: Default: `None`.
- `html_sha256: str | None`: Default: `None`.
- `raw_file: str | None`: Default: `None`.
- `parser_version: str`: Default: `'2'`.
- `website_updates: dict[str, str]`: Default: `{}`.

### `BuildCardData`

Validated build input preserving source conditions, review state, diagnostics, and render data.

Fields:

- `schema_version: Literal[1]`: Default: `1`.
- `generated_at: datetime`: Required.
- `source: str`: Required.
- `source_meta: SourceMeta | None`: Default: `None`.
- `review: ReviewInfo`: Default factory: `ReviewInfo()`.
- `character: CharacterIdentity`: Required.
- `build_name: str | None`: Default: `None`.
- `stats: CharacterStats`: Default factory: `CharacterStats()`.
- `light_cones: list[LightConeRecommendation]`: Default: `[]`.
- `relic_sets: list[RelicWeightGroup]`: Default: `[]`.
- `mixed_relic_sets: list[AssetRef]`: Default: `[]`.
- `main_stats: list[StatChoice]`: Default: `[]`.
- `substats: list[str]`: Default: `[]`.
- `substats_raw: str | None`: Default: `None`.
- `stat_targets: list[StatTarget]`: Default: `[]`.
- `stat_target_notes: list[str]`: Default: `[]`.
- `trace_priority: TracePriority`: Default factory: `TracePriority()`.
- `trace_bonuses: list[TraceBonus]`: Default: `[]`.
- `skills: list[SkillInfo]`: Default: `[]`.
- `major_traces: list[SkillInfo]`: Default: `[]`.
- `investment: InvestmentGuide`: Default factory: `InvestmentGuide()`.
- `review_notes: list[str]`: Default: `[]`.
- `editorial_teams: list[EditorTeam]`: Default: `[]`.
- `synergies: list[Synergy]`: Default: `[]`.
- `synergy_intro: str | None`: Default: `None`.
- `teams: list[TeamMode]`: Default: `[]`.
- `team_comments: list[str]`: Default: `[]`.
- `notes: list[str]`: Default: `[]`.
- `warnings: list[str]`: Default: `[]`.
- `diagnostics: dict[str, bool]`: Default: `{}`.

#### `source_is_reviewable`

```python
def source_is_reviewable(value: str) -> str:
    ...
```

Reject blank source identifiers with ValueError before accepting a build.

#### `to_json_dict`

```python
def to_json_dict() -> dict[str, Any]:
    ...
```

Return a JSON-compatible build payload, retaining explicit null fields.

### `TeamIndex`

Store a generated cross-character team index and the draft entries omitted from it.

Fields:

- `schema_version: Literal[1]`: Default: `1`.
- `generated_at: datetime`: Required.
- `review: ReviewInfo`: Default factory: `ReviewInfo()`.
- `characters: dict[str, dict[str, Any]]`: Default: `{}`.
- `skipped: list[dict[str, str]]`: Default: `[]`.

## Review and weighting enums

### `ReviewStatus`

Distinguish an unreviewed draft from an explicitly approved build.

- `ReviewStatus.DRAFT`: `'draft'`.
- `ReviewStatus.APPROVED`: `'approved'`.

### `WeightClass`

Preserve source recommendation categories without converting them into numerical scores.

- `WeightClass.BEST`: `'best'`.
- `WeightClass.ALTERNATIVE`: `'alternative'`.
- `WeightClass.GENERAL`: `'general'`.
- `WeightClass.SPECIFIC`: `'specific'`.
- `WeightClass.SPECIALIST`: `'specialist'`.

## Redeem codes and tier data

### `Reward`

One reward granted by a redeem code.

Fields:

- `name: str`: Required.
- `count: int`: Required.
- `url: str`: Required.

### `RedeemCode`

One active redeem code and all rewards it grants.

Fields:

- `code: str`: Required.
- `redeem_url: str`: Required.
- `rewards: list[Reward]`: Required.

### `RoleHeader`

Identify one tier-list role column and its display name.

Fields:

- `key: str`: Required.
- `name: str`: Required.

### `TierCharacter`

Store a tier-listed character with portrait, form, tags, and rating-change marks.

Fields:

- `name: str`: Required.
- `slug: str`: Required.
- `icon_url: str`: Required.
- `element: str`: Required.
- `rarity: int`: Required.
- `eidolon: str`: Required.
- `tags: list[str]`: Required.
- `marks: list[str]`: Required.

#### `url`

```python
url: str
```

Return the public Prydwen character URL for this source slug.

### `TierRole`

Group characters sharing one role within a tier.

Fields:

- `key: str`: Required.
- `name: str`: Required.
- `characters: list[TierCharacter]`: Required.

### `Tier`

Group the role columns for one named source tier.

Fields:

- `name: str`: Required.
- `key: str`: Required.
- `roles: list[TierRole]`: Required.

### `TierGroup`

Group tiers under the source apex, meta, niche, or forgotten heading.

Fields:

- `key: str`: Required.
- `name: str`: Required.
- `tiers: list[Tier]`: Required.

### `TierListData`

Store one mode-specific tier list with update metadata, role headers, and source URL.

Fields:

- `mode: str`: Required.
- `mode_key: str`: Required.
- `updated: str | None`: Required.
- `roles: list[RoleHeader]`: Required.
- `groups: list[TierGroup]`: Required.
- `source: str`: Default: `'https://www.prydwen.gg/star-rail/tier-list'`.

#### `tiers`

```python
tiers: list[Tier]
```

Return tiers in source group order as a flattened list.
