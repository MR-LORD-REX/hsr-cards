# Nanoka models

Field names and defaults below reflect the repository code. `Required` means the provider/model constructor must supply that field; optional fields show their default. Pydantic models support `model_validate(payload)`, `model_dump()`, and `model_dump_json()`. Use `model_dump(mode="json")` for JSON-compatible values; dataclasses instead expose their typed attributes directly.

Import public response models from `hsr_cards.providers.nanoka.models`; the legacy `hsr_cards.nanoka.models` path remains compatible. Domain query wrappers are documented separately in [results](results.md). Nanoka models preserve unknown upstream fields so provider data can evolve.

## Common values

### `NanokaModel`

Tolerant base model: new upstream keys are retained, never rejected.

### `LocalizedText`

Optional English, Chinese, Japanese, and Korean text fields.

get() resolves supported locale aliases, strips ruby annotations, and permits
other-language fallback when requested.

Fields:

- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.

#### `get`

```python
def get(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return text for locale, or None if absent and no allowed fallback exists.

Locale aliases are accepted; fallback=True tries en/zh/ja/ko. Game ruby
annotations are removed. Invalid locale aliases raise ValueError; no IO occurs.

### `NamedEntry`

A small provider object carrying optional identity, text, and effect parameters.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `param: list[float | int]`: Default: `[]`.
- `param_list: list[float | int]`: Default: `[]`.

### `MaterialCost`

A required numeric material item ID and quantity with optional rarity metadata.

Fields:

- `item_id: int`: Required.
- `item_num: int`: Required.
- `rarity: str | None`: Default: `None`.

## Characters

### `CharacterSummary`

A catalog character identity with multilingual names and release metadata.

Numeric id is required; an absent release timestamp denotes a beta entry.
Path/element fields accept the provider baseType/damageType aliases.

Fields:

- `id: int`: Required.
- `release: int | None`: Default: `None`.
- `icon: str | None`: Default: `None`.
- `rank: str | None`: Default: `None`.
- `base_type: str | None`: Default: `None`.
- `damage_type: str | None`: Default: `None`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `enhance: list[Any]`: Default: `[]`.

#### `display_name`

```python
def display_name(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the requested locale name with optional en/zh/ja/ko fallback.

Locale aliases are accepted. Return None if absent; invalid aliases raise
ValueError. Game ruby markup is removed without performing IO.

#### `element`

```python
element: str | None
```

Return the lowercase damage element, or None if absent.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> CharacterSummary:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `is_beta`

```python
is_beta: bool
```

Return whether the entry has no published release timestamp.

#### `name`

```python
name: str | None
```

Return the English display name with other-language fallback, or None.

#### `path`

```python
path: str | None
```

Return the normalized display path, or None when no path is supplied.

#### `path_codename`

```python
path_codename: str | None
```

Return the normalized provider path codename, or None if absent.

#### `release_datetime`

```python
release_datetime: datetime | None
```

Return the published Unix release timestamp as UTC, or None.

#### `released`

```python
released: bool
```

Return whether a release timestamp is published.

#### `stars`

```python
stars: int | None
```

Return numeric rarity stars, or None when the provider rarity is unknown.

### `CharacterRank`

An eidolon or additional-rank effect with its text, icon, and parameters.

Numeric id identifies the rank; optional metadata and unknown fields are
retained without resolving or downloading the icon.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `icon: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.
- `extra: dict[str, Any]`: Default: `{}`.

### `SkillLevel`

One published character skill level and its description parameter array.

Fields:

- `level: int | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

### `SkillExtra`

An additional skill text block with alternate param/param_list payloads.

Fields:

- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `param: list[float | int]`: Default: `[]`.
- `param_list: list[float | int]`: Default: `[]`.

### `CharacterSkill`

A character skill with combat costs, type labels, extras, and level parameters.

Numeric id is required. Level entries remain keyed by provider strings;
missing type labels can denote an enhanced or split skill variant.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `simple_desc: str | None`: Default: `None`.
- `type: str | None`: Default: `None`.
- `type_name: str | None`: Default: `None`.
- `tag: str | None`: Default: `None`.
- `sp_base: int | None`: Default: `None`.
- `bp_need: int | None`: Default: `None`.
- `bp_add: int | None`: Default: `None`.
- `show_stance_list: list[float | int]`: Default: `[]`.
- `skill_combo_value_delta: float | None`: Default: `None`.
- `related_ex_rank_id_list: list[int]`: Default: `[]`.
- `extra: dict[str, SkillExtra]`: Default: `{}`.
- `level: dict[str, SkillLevel]`: Default: `{}`.

#### `is_attack`

```python
is_attack: bool
```

Return whether the skill belongs to a standard combat/technique type.

#### `max_level`

```python
max_level: int | None
```

Return the highest numeric skill level, or None if no levels exist.

#### `params_at`

```python
def params_at(level: int) -> list[float | int] | None:
    ...
```

Return the published parameter array for numeric skill level, or None if absent.

### `SkillTreeLevel`

One trace level with unlock requirements, costs, bonuses, and display metadata.

Retain both legacy textual and newer numeric point-trigger keys. Missing
optional fields stay absent instead of inventing unlock or stat requirements.

Fields:

- `anchor: str | None`: Default: `None`.
- `avatar_promotion_limit: int | None`: Default: `None`.
- `avatar_level_limit: int | None`: Default: `None`.
- `default_unlock: bool`: Default: `False`.
- `icon: str | None`: Default: `None`.
- `level_up_skill_id: list[int]`: Default: `[]`.
- `material_list: list[MaterialCost]`: Default: `[]`.
- `max_level: int | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.
- `point_id: int | None`: Default: `None`.
- `point_name: str | None`: Default: `None`.
- `point_desc: str | None`: Default: `None`.
- `point_trigger_key: int | str | None`: Default: `None`.
- `point_type: int | None`: Default: `None`.
- `pre_point: list[str | int]`: Default: `[]`.
- `status_add_list: list[dict[str, Any]]`: Default: `[]`.
- `extra: dict[str, Any]`: Default: `{}`.

### `CharacterTrace`

Trace levels grouped under one provider point identifier.

The first defined level metadata supplies its display text, icon, and point
type; point types distinguish minor traces, major traces, and bonus abilities.

Fields:

- `point: str`: Required.
- `levels: list[SkillTreeLevel]`: Default: `[]`.

#### `description`

```python
description: str | None
```

Return the first published trace-level description, or None.

#### `icon`

```python
icon: str | None
```

Return the first published trace-level icon, or None when absent.

#### `is_bonus_ability`

```python
is_bonus_ability: bool
```

Return whether the trace point type denotes a bonus ability (3).

#### `is_major_trace`

```python
is_major_trace: bool
```

Return whether the trace point type denotes a major trace (2).

#### `is_minor_trace`

```python
is_minor_trace: bool
```

Return whether the trace point type denotes a minor trace (1).

#### `name`

```python
name: str | None
```

Return the first published trace-level name, or None.

#### `point_type`

```python
point_type: int | None
```

Return the first defined trace point type, or None if every level omits it.

### `VoiceActors`

Optional Chinese, Japanese, Korean, and English voice-actor credits.

Fields:

- `chinese: str | None`: Default: `None`.
- `japanese: str | None`: Default: `None`.
- `korean: str | None`: Default: `None`.
- `english: str | None`: Default: `None`.

### `CharacterInfo`

Character faction, voice actors, stories, and published voice-line metadata.

Fields:

- `camp: str | None`: Default: `None`.
- `va: VoiceActors`: Default factory: `VoiceActors()`.
- `stories: dict[str, str | None]`: Default: `{}`.
- `voicelines: list[dict[str, Any]]`: Default: `[]`.

### `CharacterStat`

Base and additive character stats, promotion metadata, and material costs.

Computed ATK/DEF/HP add available components and retain None when both are
missing; this model does not apply equipment or combat buffs.

Fields:

- `attack_base: float | None`: Default: `None`.
- `attack_add: float | None`: Default: `None`.
- `defence_base: float | None`: Default: `None`.
- `defence_add: float | None`: Default: `None`.
- `hp_base: float | None`: Default: `None`.
- `hp_add: float | None`: Default: `None`.
- `speed_base: float | None`: Default: `None`.
- `critical_chance: float | None`: Default: `None`.
- `critical_damage: float | None`: Default: `None`.
- `base_aggro: float | None`: Default: `None`.
- `cost: list[MaterialCost]`: Default: `[]`.
- `promotion: int | None`: Default: `None`.

#### `attack`

```python
attack: float | None
```

Return base plus additive ATK, retaining None when both values are absent.

#### `defence`

```python
defence: float | None
```

Return base plus additive DEF, retaining None when both values are absent.

#### `hp`

```python
hp: float | None
```

Return base plus additive HP, retaining None when both values are absent.

### `CharacterRelicBuild`

Provider relic/planar recommendations, main stats, and preferred substats.

Keep the ordered set-ID recommendations and provider property groups;
helpers expose the first recommended sets and slot-specific main-stat data.

Fields:

- `avatar_id: int | None`: Default: `None`.
- `set4_id_list: list[int]`: Default: `[]`.
- `set2_id_list: list[int]`: Default: `[]`.
- `property_list3: list[str]`: Default: `[]`.
- `property_list4: list[str]`: Default: `[]`.
- `property_list5: list[str]`: Default: `[]`.
- `property_list6: list[str]`: Default: `[]`.
- `property_list: list[dict[str, Any]]`: Default: `[]`.
- `sub_affix_property_list: list[str]`: Default: `[]`.
- `score_rank_list: list[float | int]`: Default: `[]`.

#### `main_stats`

```python
main_stats: dict[str, list[str]]
```

Return main-stat recommendations grouped by relic slot; omitted slots stay absent.

#### `planar_set`

```python
planar_set: int | None
```

Return the first two-piece planar recommendation ID, or None if unavailable.

#### `primary_set`

```python
primary_set: int | None
```

Return the first four-piece relic recommendation ID, or None if unavailable.

### `CharacterTeam`

A recommended leading avatar, ordered team members, and backup groups.

The members accessor combines the leading avatar with member_list without
resolving IDs into character objects.

Fields:

- `avatar_id: int | None`: Default: `None`.
- `team_id: int | None`: Default: `None`.
- `position: int | None`: Default: `None`.
- `member_list: list[int]`: Default: `[]`.
- `backup_list1: list[int]`: Default: `[]`.
- `backup_list2: list[int]`: Default: `[]`.
- `backup_list3: list[int]`: Default: `[]`.
- `backup_group_list1: list[Any]`: Default: `[]`.
- `backup_group_list2: list[Any]`: Default: `[]`.
- `backup_group_list3: list[Any]`: Default: `[]`.

#### `members`

```python
members: list[int]
```

Return the leading avatar and other team members, preserving their order.

### `CharacterDetail`

A complete character document containing skills, traces, ranks, stats, and builds.

Nested mappings preserve provider IDs and unknown fields. Optional memosprite,
enhanced-skill, lore, equipment, team, and skin data remain available as published.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `chara_info: CharacterInfo`: Default factory: `CharacterInfo()`.
- `rarity: str | None`: Default: `None`.
- `avatar_vo_tag: str | None`: Default: `None`.
- `sp_need: int | None`: Default: `None`.
- `base_type: str | None`: Default: `None`.
- `damage_type: str | None`: Default: `None`.
- `ranks: dict[str, CharacterRank]`: Default: `{}`.
- `ex_ranks: dict[str, CharacterRank]`: Default: `{}`.
- `skills: dict[str, CharacterSkill]`: Default: `{}`.
- `skill_trees: dict[str, dict[str, SkillTreeLevel]]`: Default: `{}`.
- `enhanced: dict[str, Any]`: Default: `{}`.
- `memosprite: dict[str, Any]`: Default: `{}`.
- `unique: dict[str, Any]`: Default: `{}`.
- `stats: dict[str, CharacterStat]`: Default: `{}`.
- `relics: CharacterRelicBuild | None`: Default: `None`.
- `lightcones: list[int]`: Default: `[]`.
- `teams: list[CharacterTeam]`: Default: `[]`.
- `skin: dict[str, Any]`: Default: `{}`.

#### `basic_attack`

```python
basic_attack: CharacterSkill | None
```

Return the first Normal skill, or None if absent.

#### `bonus_abilities`

```python
bonus_abilities: list[CharacterTrace]
```

Return traces whose provider point type is bonus ability (3).

#### `eidolons`

```python
eidolons: list[CharacterRank]
```

Return eidolon models sorted by numeric rank ID.

#### `element`

```python
element: str | None
```

Return the lowercase damage element, or None if absent.

#### `enhanced_skills`

```python
enhanced_skills: list[CharacterSkill]
```

Return unlabeled skill entries used for enhanced or split skill variants.

#### `extra_ranks`

```python
extra_ranks: list[CharacterRank]
```

Return additional rank models sorted by ID.

#### `major_traces`

```python
major_traces: list[CharacterTrace]
```

Return traces whose provider point type is major trace (2).

#### `max_stat`

```python
max_stat: CharacterStat | None
```

Return the highest numeric promotion stat block, or None if no stats exist.

#### `minor_traces`

```python
minor_traces: list[CharacterTrace]
```

Return traces whose provider point type is minor trace (1).

#### `path`

```python
path: str | None
```

Return the normalized display path, or None when no path is supplied.

#### `path_codename`

```python
path_codename: str | None
```

Return the normalized provider path codename, or None if absent.

#### `skill`

```python
skill: CharacterSkill | None
```

Return the first BPSkill entry, or None if absent.

#### `stars`

```python
stars: int | None
```

Return numeric rarity stars, or None when the provider rarity is unknown.

#### `talent`

```python
talent: CharacterSkill | None
```

Return the first skill labeled Talent, or None if absent.

#### `technique`

```python
technique: CharacterSkill | None
```

Return the first Maze skill, or None if absent.

#### `traces`

```python
traces: list[CharacterTrace]
```

Return grouped trace-level models in provider point order.

#### `ultimate`

```python
ultimate: CharacterSkill | None
```

Return the first Ultra skill, or None if absent.

## Light Cones

### `LightConeSummary`

A light-cone catalog identity with multilingual names, path, rarity, and ATK.

Numeric id is required and baseType is accepted as the provider path alias.

Fields:

- `id: int`: Required.
- `rank: str | None`: Default: `None`.
- `base_type: str | None`: Default: `None`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `atk: float | int | None`: Default: `None`.
- `desc: str | None`: Default: `None`.

#### `display_name`

```python
def display_name(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the requested locale name with optional en/zh/ja/ko fallback.

Locale aliases are accepted. Return None if absent; invalid aliases raise
ValueError. Game ruby markup is removed without performing IO.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> LightConeSummary:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `name`

```python
name: str | None
```

Return the English display name with other-language fallback, or None.

#### `path`

```python
path: str | None
```

Return the normalized display path, or None when no path is supplied.

#### `path_codename`

```python
path_codename: str | None
```

Return the normalized provider path codename, or None if absent.

#### `stars`

```python
stars: int | None
```

Return numeric rarity stars, or None when the provider rarity is unknown.

### `RefinementLevel`

One superimposition level and its published effect parameter array.

Fields:

- `level: int | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

### `LightConeRefinement`

A light-cone effect description with parameters for each superimposition level.

Provider string keys are retained; levels exposes numeric keys for valid entries.

Fields:

- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `level: dict[str, RefinementLevel]`: Default: `{}`.

#### `levels`

```python
levels: dict[int, list[float | int]]
```

Return refinement parameters keyed by numeric superimposition level.

### `PromotionCost`

A light-cone promotion material ID and quantity using the shared cost schema.

Fields:

- `item_id: int`: Required.
- `item_num: int`: Required.
- `rarity: str | None`: Default: `None`.

### `LightConeStat`

A light-cone promotion stat block with level gates, base/additive stats, and costs.

The required equipment_id identifies the cone; optional fields retain missing
data rather than calculating a character-specific contribution.

Fields:

- `equipment_id: int`: Required.
- `promotion: int | None`: Default: `None`.
- `promotion_cost_list: list[PromotionCost]`: Default: `[]`.
- `player_level_require: int | None`: Default: `None`.
- `world_level_require: int | None`: Default: `None`.
- `max_level: int | None`: Default: `None`.
- `base_hp: float | None`: Default: `None`.
- `base_hp_add: float | None`: Default: `None`.
- `base_attack: float | None`: Default: `None`.
- `base_attack_add: float | None`: Default: `None`.
- `base_defence: float | None`: Default: `None`.
- `base_defence_add: float | None`: Default: `None`.

### `LightConeDetail`

A light-cone detail document with effect refinements and promotion stat blocks.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `rarity: str | None`: Default: `None`.
- `base_type: str | None`: Default: `None`.
- `refinements: LightConeRefinement | None`: Default: `None`.
- `stats: list[LightConeStat]`: Default: `[]`.

#### `path`

```python
path: str | None
```

Return the normalized display path, or None when no path is supplied.

#### `path_codename`

```python
path_codename: str | None
```

Return the normalized provider path codename, or None if absent.

#### `stars`

```python
stars: int | None
```

Return numeric rarity stars, or None when the provider rarity is unknown.

## Relics

### `RelicSetEffect`

A relic-set bonus with required piece count, localized text, and parameters.

Explicit desc takes precedence over language fields; ParamList is accepted as
the provider parameter alias.

Fields:

- `pieces: int`: Required.
- `desc: str | None`: Default: `None`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

#### `description`

```python
description: str | None
```

Return the default-language effect description, or None when absent.

#### `display_desc`

```python
def display_desc(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the explicit description, otherwise localized effect text.

Locale aliases are accepted; fallback=True tries en/zh/ja/ko. Return None
when absent and raise ValueError for invalid aliases. No IO occurs.

### `RelicSetSummary`

A relic-set catalog identity with multilingual names and piece-count effect groups.

Fields:

- `id: int`: Required.
- `icon: str | None`: Default: `None`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `set: dict[str, dict[str, Any]]`: Default: `{}`.

#### `display_name`

```python
def display_name(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the requested locale name with optional en/zh/ja/ko fallback.

Locale aliases are accepted. Return None if absent; invalid aliases raise
ValueError. Game ruby markup is removed without performing IO.

#### `effects`

```python
effects: list[RelicSetEffect]
```

Return parsed set effects ordered by their required piece count.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> RelicSetSummary:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `name`

```python
name: str | None
```

Return the English display name with other-language fallback, or None.

### `RelicPart`

An individual relic piece with optional ID, name, lore, description, and icon.

slot resolves known relic slots from the final ID digit without loading assets.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `story: str | None`: Default: `None`.
- `icon: str | None`: Default: `None`.

#### `slot`

```python
slot: str | None
```

Resolve a relic slot from the final item-ID digit, or None if unknown.

### `RelicSetEffectDetail`

A detailed set bonus with required piece count, description, and effect parameters.

Fields:

- `pieces: int`: Required.
- `desc: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

### `RelicSetDetail`

A relic-set document containing keyed pieces and required-piece effect definitions.

piece_list fills omitted piece IDs from numeric mapping keys; effects exposes
parsed bonuses ordered by piece count.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `icon: str | None`: Default: `None`.
- `parts: dict[str, RelicPart]`: Default: `{}`.
- `require_num: dict[str, dict[str, Any]]`: Default: `{}`.

#### `effects`

```python
effects: list[RelicSetEffectDetail]
```

Return parsed set effects ordered by their required piece count.

#### `piece_list`

```python
piece_list: list[RelicPart]
```

Return relic parts, filling missing IDs from numeric provider mapping keys.

## Monsters

### `MonsterSummary`

A catalog monster identity with multilingual names, rank, weaknesses, and variant IDs.

Numeric id is required; child IDs link stage variants to their catalog base
monster without resolving or loading detail documents.

Fields:

- `id: int`: Required.
- `rank: str | None`: Default: `None`.
- `camp: int | None`: Default: `None`.
- `icon: str | None`: Default: `None`.
- `child: list[int]`: Default: `[]`.
- `weak: list[str]`: Default: `[]`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.

#### `display_name`

```python
def display_name(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the requested locale name with optional en/zh/ja/ko fallback.

Locale aliases are accepted. Return None if absent; invalid aliases raise
ValueError. Game ruby markup is removed without performing IO.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> MonsterSummary:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `name`

```python
name: str | None
```

Return the English display name with other-language fallback, or None.

#### `weaknesses`

```python
weaknesses: list[str]
```

Return lowercase weakness elements, or [] when no weaknesses exist.

### `MonsterStats`

A numeric monster base-stat record from the provider scaling catalog.

Accept the provider PascalCase stat aliases. Stage, difficulty, phase, and
corrosion multipliers are applied by services rather than this data model.

Fields:

- `id: int | None`: Default: `None`.
- `rank: str | None`: Default: `None`.
- `attack_base: float | int | None`: Default: `None`.
- `defence_base: float | int | None`: Default: `None`.
- `hp_base: float | int | None`: Default: `None`.
- `speed_base: float | int | None`: Default: `None`.
- `stance_base: float | int | None`: Default: `None`.
- `status_resistance_base: float | None`: Default: `None`.
- `child: list[dict[str, Any]]`: Default: `[]`.

### `EliteGroup`

An elite-group ID and its ATK/DEF/HP/speed/toughness scaling ratios.

Ratios default to one when omitted and accept provider PascalCase aliases.

Fields:

- `elite_group: int`: Required.
- `attack_ratio: float`: Default: `1`.
- `defence_ratio: float`: Default: `1`.
- `hp_ratio: float`: Default: `1`.
- `speed_ratio: float`: Default: `1`.
- `stance_ratio: float`: Default: `1`.

### `HardLevelGroup`

Difficulty-group and monster-level scaling ratios with combat-power metadata.

The group ID and level are required; omitted ratios default to one. This
model supplies factors without calculating final encounter stats.

Fields:

- `hard_level_group: int`: Required.
- `level: int`: Required.
- `attack_ratio: float`: Default: `1`.
- `defence_ratio: float`: Default: `1`.
- `hp_ratio: float`: Default: `1`.
- `speed_ratio: float`: Default: `1`.
- `stance_ratio: float`: Default: `1`.
- `combat_power_list: list[float | int]`: Default: `[]`.

### `InfiniteEliteGroup`

The PF infinite-wave specialization of the shared elite scaling-ratio model.

Fields:

- `elite_group: int`: Required.
- `attack_ratio: float`: Default: `1`.
- `defence_ratio: float`: Default: `1`.
- `hp_ratio: float`: Default: `1`.
- `speed_ratio: float`: Default: `1`.
- `stance_ratio: float`: Default: `1`.

### `MonsterVariant`

A stage monster variant with stat modifiers, weaknesses, resistances, and skills.

Numeric id is required. Group references and optional ratios/flat values remain
unapplied until an encounter service resolves the stage context.

Fields:

- `id: int`: Required.
- `attack_modify_ratio: float | None`: Default: `None`.
- `defence_modify_ratio: float | None`: Default: `None`.
- `elite_group: int | None`: Default: `None`.
- `hp_modify_ratio: float | None`: Default: `None`.
- `speed_modify_ratio: float | None`: Default: `None`.
- `speed_modify_value: float | None`: Default: `None`.
- `stance_modify_ratio: float | None`: Default: `None`.
- `stance_modify_value: float | None`: Default: `None`.
- `stance_weak_list: list[str]`: Default: `[]`.
- `hard_level_group: int | None`: Default: `None`.
- `damage_type_resistance: list[dict[str, Any]]`: Default: `[]`.
- `skill_list: list[dict[str, Any] | int]`: Default: `[]`.

### `MonsterDetail`

A monster detail document with base combat stats, variant records, art, and drops.

Numeric id is required; weaknesses exposes the first variant weakness list.
Final stage HP and phase behavior are resolved outside this model.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `monster_camp_id: int | None`: Default: `None`.
- `attack_base: float | None`: Default: `None`.
- `critical_damage_base: float | None`: Default: `None`.
- `defence_base: float | None`: Default: `None`.
- `hp_base: float | None`: Default: `None`.
- `initial_delay_ratio: float | None`: Default: `None`.
- `image_path: str | None`: Default: `None`.
- `minimum_fatigue_ratio: float | None`: Default: `None`.
- `rank: str | None`: Default: `None`.
- `speed_base: float | None`: Default: `None`.
- `stance_base: float | None`: Default: `None`.
- `stance_count: int | None`: Default: `None`.
- `status_resistance_base: float | None`: Default: `None`.
- `child: list[MonsterVariant]`: Default: `[]`.
- `drop: list[Any]`: Default: `[]`.

#### `variants`

```python
variants: list[MonsterVariant]
```

Return the published monster variant models.

#### `weaknesses`

```python
weaknesses: list[str]
```

Return lowercase weaknesses from the first monster variant, or [] if absent.

## Schedules

### `MazeSchedule`

An endgame catalog season with multilingual names and separate live/test windows.

Numeric id is required; optional mode/version describe provider context.
UTC date accessors prefer live boundaries and expose test/deployment dates
separately. Missing dates stay unknown instead of inventing a live interval.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `begin: str | None`: Default: `None`.
- `end: str | None`: Default: `None`.
- `live_begin: str | None`: Default: `None`.
- `live_end: str | None`: Default: `None`.
- `param: list[float | int]`: Default: `[]`.
- `mode: str | None`: Default: `None`.
- `version: str | None`: Default: `None`.

#### `begins_at`

```python
begins_at: datetime | None
```

Return the UTC live start, falling back to the test/deployment start.

#### `display_name`

```python
def display_name(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the requested locale name with optional en/zh/ja/ko fallback.

Locale aliases are accepted. Return None if absent; invalid aliases raise
ValueError. Game ruby markup is removed without performing IO.

#### `ends_at`

```python
ends_at: datetime | None
```

Return the UTC live end, falling back to the test/deployment end.

#### `from_entry`

```python
def from_entry(
    identifier: str | int,
    payload: dict[str, Any],
    *,
    mode: str | None = None,
    version: str | None = None,
) -> MazeSchedule:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Optional mode/version metadata is merged with payload fields. Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `has_live_window`

```python
has_live_window: bool
```

Return whether both authoritative live date fields are published.

#### `has_schedule`

```python
has_schedule: bool
```

Return whether at least one effective start/end boundary is available.

#### `is_live`

```python
is_live: bool
```

Return whether the current UTC time lies within the effective start/end window.

#### `is_live_at`

```python
def is_live_at(when: datetime | None = None) -> bool:
    ...
```

Return whether a supplied moment lies inclusively within the effective window.

Omit when to use current UTC time; naive datetimes are interpreted as UTC.
Return False without both date boundaries. This performs no IO.

#### `is_upcoming`

```python
is_upcoming: bool
```

Return whether the effective start lies after the current UTC time.

#### `live_begins_at`

```python
live_begins_at: datetime | None
```

Return the authoritative live start as UTC, or None if absent/invalid.

#### `live_ends_at`

```python
live_ends_at: datetime | None
```

Return the authoritative live end as UTC, or None if absent/invalid.

#### `localized_name`

```python
localized_name: str | None
```

Return the default-locale schedule name with other-language fallback.

#### `test_begins_at`

```python
test_begins_at: datetime | None
```

Return the test/deployment start as UTC, or None if absent/invalid.

#### `test_ends_at`

```python
test_ends_at: datetime | None
```

Return the test/deployment end as UTC, or None if absent/invalid.

### `PeakSchedule`

Anomaly Arbitration seasons are ordered but have no date window.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `en: str | None`: Default: `None`.
- `zh: str | None`: Default: `None`.
- `ja: str | None`: Default: `None`.
- `ko: str | None`: Default: `None`.
- `begin: str | None`: Default: `None`.
- `end: str | None`: Default: `None`.
- `live_begin: str | None`: Default: `None`.
- `live_end: str | None`: Default: `None`.
- `param: list[float | int]`: Default: `[]`.
- `mode: str | None`: Default: `None`.
- `version: str | None`: Default: `None`.

#### `begins_at`

```python
begins_at: datetime | None
```

Return the UTC live start, falling back to the test/deployment start.

#### `display_name`

```python
def display_name(locale: Locale | str = Locale.EN, *, fallback: bool = True) -> str | None:
    ...
```

Return the requested locale name with optional en/zh/ja/ko fallback.

Locale aliases are accepted. Return None if absent; invalid aliases raise
ValueError. Game ruby markup is removed without performing IO.

#### `ends_at`

```python
ends_at: datetime | None
```

Return the UTC live end, falling back to the test/deployment end.

#### `from_entry`

```python
def from_entry(
    identifier: str | int,
    payload: dict[str, Any],
    *,
    mode: str | None = None,
    version: str | None = None,
) -> MazeSchedule:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Optional mode/version metadata is merged with payload fields. Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `has_live_window`

```python
has_live_window: bool
```

Return whether both authoritative live date fields are published.

#### `has_schedule`

```python
has_schedule: bool
```

Return whether at least one effective start/end boundary is available.

#### `is_live`

```python
is_live: bool
```

Return whether the current UTC time lies within the effective start/end window.

#### `is_live_at`

```python
def is_live_at(when: datetime | None = None) -> bool:
    ...
```

Return whether a supplied moment lies inclusively within the effective window.

Omit when to use current UTC time; naive datetimes are interpreted as UTC.
Return False without both date boundaries. This performs no IO.

#### `is_upcoming`

```python
is_upcoming: bool
```

Return whether the effective start lies after the current UTC time.

#### `live_begins_at`

```python
live_begins_at: datetime | None
```

Return the authoritative live start as UTC, or None if absent/invalid.

#### `live_ends_at`

```python
live_ends_at: datetime | None
```

Return the authoritative live end as UTC, or None if absent/invalid.

#### `localized_name`

```python
localized_name: str | None
```

Return the default-locale schedule name with other-language fallback.

#### `test_begins_at`

```python
test_begins_at: datetime | None
```

Return the test/deployment start as UTC, or None if absent/invalid.

#### `test_ends_at`

```python
test_ends_at: datetime | None
```

Return the test/deployment end as UTC, or None if absent/invalid.

## Endgame stages and mechanics

### `StageConfigValue`

A stage configuration key/value pair using the provider obfuscated aliases.

Fields:

- `key: str | None`: Default: `None`.
- `value: str | None`: Default: `None`.

### `MonsterSlot`

One wave group containing up to five optional ordered monster slots.

Occupied slots preserve their order and duplicates, which can represent
multiple spawns of the same monster.

Fields:

- `monster0: int | None`: Default: `None`.
- `monster1: int | None`: Default: `None`.
- `monster2: int | None`: Default: `None`.
- `monster3: int | None`: Default: `None`.
- `monster4: int | None`: Default: `None`.

#### `monster_ids`

```python
monster_ids: list[int]
```

Return occupied monster-slot IDs in slot order, retaining duplicates.

### `StageInvasion`

Additional invasion monsters in slot-shaped, direct-ID, or flat-ID form.

all_monster_ids combines the supported shapes into unique IDs in encounter order.

Fields:

- `monster_list: ForwardRef('list[MonsterSlot | StageMonster]')`: Default: `[]`.
- `monster_ids: list[int]`: Default: `[]`.

#### `all_monster_ids`

```python
all_monster_ids: list[int]
```

Return unique monster IDs, including nested wave/invasion references.

### `StageMonster`

A direct stage monster reference with optional level and base/variant IDs.

resolved_id prefers monster_id over id; missing references remain None.

Fields:

- `id: int | None`: Default: `None`.
- `level: int | None`: Default: `None`.
- `monster_id: int | None`: Default: `None`.

#### `resolved_id`

```python
resolved_id: int | None
```

Return monster_id when defined, otherwise the entry ID.

### `StageEvent`

A combat event with wave monsters, stage scaling, configuration, and invasion data.

Retain both wave-shaped monster_list and optional flat monster_ids. Difficulty
ratios are references here; card services compute final HP separately.

Fields:

- `stage_id: int | None`: Default: `None`.
- `stage_type: str | None`: Default: `None`.
- `stage_name: str | int | None`: Default: `None`.
- `hard_level_group: int | None`: Default: `None`.
- `level: int | None`: Default: `None`.
- `elite_group: int | None`: Default: `None`.
- `max_teammate_count: int | None`: Default: `None`.
- `monster_list: list[MonsterSlot]`: Default: `[]`.
- `stage_config_data: list[StageConfigValue]`: Default: `[]`.
- `invasion: StageInvasion | None`: Default: `None`.
- `monster_ids: list[int]`: Default: `[]`.
- `release: bool | None`: Default: `None`.

#### `all_monster_ids`

```python
all_monster_ids: list[int]
```

Return unique monster IDs, including nested wave/invasion references.

#### `wave_count`

```python
wave_count: int
```

Return the number of published monster waves.

### `InfiniteWave`

A PF infinite-wave definition with monster groups, spawn limits, and modifiers.

Keep the elite-group and ability parameter references used for wave HP and
mechanics calculations; this model performs no calculations or asset loading.

Fields:

- `infinite_wave_id: int | None`: Default: `None`.
- `monster_group_id_list: list[int]`: Default: `[]`.
- `max_monster_count: int | None`: Default: `None`.
- `max_teammate_count: int | None`: Default: `None`.
- `ability: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.
- `elite_group: int | None`: Default: `None`.

### `BossConfigTag`

A boss mechanic tag with text, parameters, skill reference, and nested tags.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `param: list[float | int]`: Default: `[]`.
- `param_fix: list[float | int]`: Default: `[]`.
- `skill_id: int | None`: Default: `None`.
- `child: list[BossConfigTag]`: Default: `[]`.

### `BossPhase`

A boss phase description with response hints, difficulty, and referenced skills.

Fields:

- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `answer: str | None`: Default: `None`.
- `difficulty: int | None`: Default: `None`.
- `skill_list: list[int]`: Default: `[]`.

### `BossConfig`

Boss difficulty choices, mechanic tags, guides, and phase descriptions.

Collections remain in provider order so renderers can present all published
mechanics without fetching or selecting a season.

Fields:

- `difficulty: int | None`: Default: `None`.
- `difficulty_list: list[int]`: Default: `[]`.
- `tag_list: list[BossConfigTag]`: Default: `[]`.
- `difficulty_guide_list: list[BossConfigTag]`: Default: `[]`.
- `text_guide_list: list[str]`: Default: `[]`.
- `phase_list: list[BossPhase]`: Default: `[]`.

### `StageChallenge`

A score/objective condition with scalar or list-shaped description parameters.

params accepts either param representation and falls back to param_list.

Fields:

- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `param: float | int | list[float | int] | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

#### `params`

```python
params: list[float | int]
```

Return list/scalar parameters, falling back to the published param_list.

### `StageLevel`

One endgame floor or continuation record with challenges and combat nodes.

Retain base and numbered node fields for bosses, events, infinite waves, NPC
monsters, recommended elements, and mechanics. Continuation IDs are data;
services decide how records compose into a rendered floor.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `pre_id: int | None`: Default: `None`.
- `pre_level_id: int | None`: Default: `None`.
- `challenge: list[StageChallenge]`: Default: `[]`.
- `challenge_special: list[StageChallenge]`: Default: `[]`.
- `countdown: int | None`: Default: `None`.
- `damage_type: list[str]`: Default: `[]`.
- `damage_type1: list[str]`: Default: `[]`.
- `damage_type2: list[str]`: Default: `[]`.
- `boss_monster_id: int | None`: Default: `None`.
- `boss_monster_id1: int | None`: Default: `None`.
- `boss_monster_id2: int | None`: Default: `None`.
- `boss_monster_id_skill_list: list[int]`: Default: `[]`.
- `boss_monster_id1_skill_list: list[int]`: Default: `[]`.
- `boss_monster_id2_skill_list: list[int]`: Default: `[]`.
- `boss_monster_config: BossConfig | None`: Default: `None`.
- `boss_monster_config1: BossConfig | None`: Default: `None`.
- `boss_monster_config2: BossConfig | None`: Default: `None`.
- `event_id_list: list[StageEvent]`: Default: `[]`.
- `event_id_list1: list[StageEvent]`: Default: `[]`.
- `event_id_list2: list[StageEvent]`: Default: `[]`.
- `infinite_list: dict[str, InfiniteWave]`: Default: `{}`.
- `infinite_list1: dict[str, InfiniteWave]`: Default: `{}`.
- `infinite_list2: dict[str, InfiniteWave]`: Default: `{}`.
- `npc_monster_id_list: list[int]`: Default: `[]`.
- `npc_monster_id_list1: list[int]`: Default: `[]`.
- `npc_monster_id_list2: list[int]`: Default: `[]`.
- `maze_group_id1: int | None`: Default: `None`.
- `maze_group_id2: int | None`: Default: `None`.
- `tag_list: list[NamedEntry]`: Default: `[]`.

#### `all_events`

```python
all_events: list[StageEvent]
```

Return the same stage event list exposed by events.

#### `all_monster_ids`

```python
all_monster_ids: list[int]
```

Return unique monster IDs, including nested wave/invasion references.

#### `boss_ids`

```python
boss_ids: list[int]
```

Return unique IDs referenced by boss definitions in encounter order.

#### `elements`

```python
elements: list[str]
```

Return unique recommended elements in lowercase and encounter order.

#### `events`

```python
events: list[StageEvent]
```

Return the published stage events in provider order.

#### `infinite_waves`

```python
infinite_waves: list[InfiniteWave]
```

Return all infinite-mode waves published in this stage.

#### `monster_ids`

```python
monster_ids: list[int]
```

Return unique referenced monster IDs in encounter order.

### `EndgameDetail`

A MOC/PF/AS season document with floors, buffs, options, and optional date bounds.

mode records the canonical provider mode. Stage and boss helpers expose parsed
data; live status requires both valid UTC detail dates.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `buff: NamedEntry | None`: Default: `None`.
- `buff_list: list[NamedEntry]`: Default: `[]`.
- `buff_list1: list[NamedEntry]`: Default: `[]`.
- `buff_list2: list[NamedEntry]`: Default: `[]`.
- `buff_list3: list[NamedEntry]`: Default: `[]`.
- `option: list[NamedEntry]`: Default: `[]`.
- `sub_option: list[NamedEntry]`: Default: `[]`.
- `begin_time: str | None`: Default: `None`.
- `end_time: str | None`: Default: `None`.
- `level: list[StageLevel]`: Default: `[]`.
- `mode: str | None`: Default: `None`.

#### `boss_ids`

```python
boss_ids: list[int]
```

Return unique boss IDs for the designated boss stage, or [] if unavailable.

#### `boss_stage`

```python
boss_stage: StageLevel | None
```

Return the last nonempty stage, or None when no boss stage exists.

#### `ends_at`

```python
ends_at: datetime | None
```

Return the published detail end time as UTC, or None if absent/invalid.

#### `is_live`

```python
is_live: bool
```

Return whether the current UTC time lies within both published date boundaries.

#### `monster_ids`

```python
monster_ids: list[int]
```

Return unique referenced monster IDs in encounter order.

#### `stages`

```python
stages: list[StageLevel]
```

Return stage models in published encounter order.

#### `starts_at`

```python
starts_at: datetime | None
```

Return the published detail start time as UTC, or None if absent/invalid.

### `PeakBossLevel`

The AA boss-stage specialization of the shared endgame stage model.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `pre_id: int | None`: Default: `None`.
- `pre_level_id: int | None`: Default: `None`.
- `challenge: list[StageChallenge]`: Default: `[]`.
- `challenge_special: list[StageChallenge]`: Default: `[]`.
- `countdown: int | None`: Default: `None`.
- `damage_type: list[str]`: Default: `[]`.
- `damage_type1: list[str]`: Default: `[]`.
- `damage_type2: list[str]`: Default: `[]`.
- `boss_monster_id: int | None`: Default: `None`.
- `boss_monster_id1: int | None`: Default: `None`.
- `boss_monster_id2: int | None`: Default: `None`.
- `boss_monster_id_skill_list: list[int]`: Default: `[]`.
- `boss_monster_id1_skill_list: list[int]`: Default: `[]`.
- `boss_monster_id2_skill_list: list[int]`: Default: `[]`.
- `boss_monster_config: BossConfig | None`: Default: `None`.
- `boss_monster_config1: BossConfig | None`: Default: `None`.
- `boss_monster_config2: BossConfig | None`: Default: `None`.
- `event_id_list: list[StageEvent]`: Default: `[]`.
- `event_id_list1: list[StageEvent]`: Default: `[]`.
- `event_id_list2: list[StageEvent]`: Default: `[]`.
- `infinite_list: dict[str, InfiniteWave]`: Default: `{}`.
- `infinite_list1: dict[str, InfiniteWave]`: Default: `{}`.
- `infinite_list2: dict[str, InfiniteWave]`: Default: `{}`.
- `npc_monster_id_list: list[int]`: Default: `[]`.
- `npc_monster_id_list1: list[int]`: Default: `[]`.
- `npc_monster_id_list2: list[int]`: Default: `[]`.
- `maze_group_id1: int | None`: Default: `None`.
- `maze_group_id2: int | None`: Default: `None`.
- `tag_list: list[NamedEntry]`: Default: `[]`.

#### `all_events`

```python
all_events: list[StageEvent]
```

Return the same stage event list exposed by events.

#### `all_monster_ids`

```python
all_monster_ids: list[int]
```

Return unique monster IDs, including nested wave/invasion references.

#### `boss_ids`

```python
boss_ids: list[int]
```

Return unique IDs referenced by boss definitions in encounter order.

#### `elements`

```python
elements: list[str]
```

Return unique recommended elements in lowercase and encounter order.

#### `events`

```python
events: list[StageEvent]
```

Return the published stage events in provider order.

#### `infinite_waves`

```python
infinite_waves: list[InfiniteWave]
```

Return all infinite-mode waves published in this stage.

#### `monster_ids`

```python
monster_ids: list[int]
```

Return unique referenced monster IDs in encounter order.

### `PeakDetail`

An AA document containing preparation stages, boss stage, and boss mechanics.

No dependable live date window is inferred. This model exposes published data
without enabling deferred AA floor-card rendering.

Fields:

- `id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `pre_level: list[StageLevel]`: Default: `[]`.
- `boss_level: StageLevel | None`: Default: `None`.
- `boss_config: BossConfig | None`: Default: `None`.
- `mode: str | None`: Default: `None`.

#### `boss_ids`

```python
boss_ids: list[int]
```

Return unique boss IDs for the designated boss stage, or [] if unavailable.

#### `boss_name`

```python
boss_name: str | None
```

Return the designated boss-stage name, falling back to the peak name.

#### `boss_stage`

```python
boss_stage: StageLevel | None
```

Return the explicit peak boss stage, or None when absent.

#### `monster_ids`

```python
monster_ids: list[int]
```

Return unique referenced monster IDs in encounter order.

#### `stages`

```python
stages: list[StageLevel]
```

Return preparation stages followed by the optional peak boss stage.

## Items and achievements

### `ItemSummary`

An item catalog entry with category, rarity, icons, lore, and source metadata.

Numeric id is required; from_entry() normalizes provider PascalCase keys.
Absent optional item fields remain None and unknown fields are retained.

Fields:

- `id: int`: Required.
- `item_name: str | None`: Default: `None`.
- `item_sub_type: str | None`: Default: `None`.
- `item_main_type: str | None`: Default: `None`.
- `purpose_type: int | None`: Default: `None`.
- `rarity: str | None`: Default: `None`.
- `item_icon_path: str | None`: Default: `None`.
- `item_figure_icon_path: str | None`: Default: `None`.
- `item_currency_icon_path: str | None`: Default: `None`.
- `item_avatar_icon_path: str | None`: Default: `None`.
- `item_desc: str | None`: Default: `None`.
- `item_bg_desc: str | None`: Default: `None`.
- `item_comefrom: list[NamedEntry]`: Default: `[]`.
- `pile_limit: int | None`: Default: `None`.

#### `desc`

```python
desc: str | None
```

Return background lore when available, otherwise the item description.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> ItemSummary:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

PascalCase keys are normalized to snake_case. Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `name`

```python
name: str | None
```

Return the localized item_name field supplied by the catalog.

#### `stars`

```python
stars: int | None
```

Return numeric rarity stars, or None when the provider rarity is unknown.

### `Achievement`

One achievement with its numeric ID, text, rarity, visibility, and parameters.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `rarity: str | None`: Default: `None`.
- `show_type: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

### `AchievementSeries`

A prioritized achievement group whose provider list field contains achievements.

Numeric id is required; items/count expose the parsed collection without
fetching individual achievements.

Fields:

- `id: int`: Required.
- `priority: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `achievements: list[Achievement]`: Default: `[]`.

#### `count`

```python
count: int
```

Return the number of achievements in this series.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> AchievementSeries:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

#### `items`

```python
items: list[Achievement]
```

Return the achievement models contained in this series.

## Currency Wars

### `CurrencyRole`

A Currency Wars role with rarity, combat position, charges, and trait IDs.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `front_back_type: str | None`: Default: `None`.
- `rarity: int | None`: Default: `None`.
- `heal_or_shield_display: str | None`: Default: `None`.
- `charge_type: list[str]`: Default: `[]`.
- `max_sp_icon: str | None`: Default: `None`.
- `trait_list: list[int]`: Default: `[]`.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> CurrencyRole:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

### `CurrencyTraitLayer`

One Currency Wars trait layer with buff text, quality, and effect parameters.

Fields:

- `id: int | None`: Default: `None`.
- `buff_name: str | None`: Default: `None`.
- `buff_desc: str | None`: Default: `None`.
- `buff_simple_desc: str | None`: Default: `None`.
- `buff_param_list: list[float | int]`: Default: `[]`.
- `quality: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

### `CurrencyTrait`

A Currency Wars trait with activation rules, effects, layers, and related traits.

Effect collections accept the provider list or mapping shapes; optional
remark/sub-trait data and unknown fields are retained.

Fields:

- `id: int`: Required.
- `activation_type: str | None`: Default: `None`.
- `icon_path: str | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `simple_desc: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.
- `effect_list: list[dict[str, Any] | int] | dict[str, Any]`: Default: `[]`.
- `layer: dict[str, CurrencyTraitLayer]`: Default: `{}`.
- `remark: dict[str, Any] | None`: Default: `None`.
- `sub_trait: dict[str, Any] | None`: Default: `None`.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> CurrencyTrait:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

### `CurrencyItem`

A Currency Wars item with effect parameters and stacking/consumption rules.

Fields:

- `id: int`: Required.
- `type: str | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.
- `icon_path: str | None`: Default: `None`.
- `consumable_rule: str | None`: Default: `None`.
- `if_stack: bool | None`: Default: `None`.
- `if_consume: bool | None`: Default: `None`.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> CurrencyItem:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

### `CurrencyAugment`

A Currency Wars augment with rarity, icon, text, and published effects.

from_entry() normalizes provider PascalCase keys before validating the model.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `rarity: str | None`: Default: `None`.
- `icon: str | None`: Default: `None`.
- `effect_list: list[Any]`: Default: `[]`.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> CurrencyAugment:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

PascalCase keys are normalized to snake_case. Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

### `CurrencyBuff`

A Currency Wars buff with rarity, icon, text, and description parameters.

from_entry() normalizes provider PascalCase keys before validating the model.

Fields:

- `id: int`: Required.
- `name: str | None`: Default: `None`.
- `desc: str | None`: Default: `None`.
- `rarity: str | None`: Default: `None`.
- `icon: str | None`: Default: `None`.
- `param_list: list[float | int]`: Default: `[]`.

#### `from_entry`

```python
def from_entry(identifier: str | int, payload: dict[str, Any]) -> CurrencyBuff:
    ...
```

Parse a provider catalog entry with a numeric identifier into this model.

PascalCase keys are normalized to snake_case. Unknown fields are retained;
invalid IDs/models raise ValueError or pydantic.ValidationError. No IO occurs.

## Versions and manifests

### `AssetInfo`

Manifest metadata for a cached CDN asset and one of its lookup aliases.

Track its cache-relative path, source URL, size, validators, and last update;
optional metadata stays None when the provider does not publish it.

Fields:

- `key: str`: Required.
- `path: str`: Required.
- `url: str`: Required.
- `relative_path: str | None`: Default: `None`.
- `size: int | None`: Default: `None`.
- `content_type: str | None`: Default: `None`.
- `etag: str | None`: Default: `None`.
- `last_modified: str | None`: Default: `None`.
- `updated_at: datetime | None`: Default: `None`.

### `NanokaVersions`

Published HSR data builds advertised by the Nanoka manifest.

Fields:

- `versions: list[str]`: Default: `[]`.
- `live_server: str | None`: Default: `None`.
- `live_beta: str | None`: Default: `None`.
- `latest: str | None`: Default: `None`.

### `CacheManifest`

Persisted completeness, version, locale, files, and validators for one cache.

Track JSON and asset completion separately, with empty collections until
downloads are recorded. Timestamps use UTC; unknown upstream fields are retained.

Fields:

- `schema_version: int`: Default: `2`.
- `version: str`: Required.
- `live_version: str | None`: Default: `None`.
- `language: Locale`: Default: `Locale.EN`.
- `created_at: datetime`: Created by the model default factory.
- `updated_at: datetime`: Created by the model default factory.
- `complete: bool`: Default: `False`.
- `assets_complete: bool`: Default: `False`.
- `root_files: list[str]`: Default: `[]`.
- `detail_files: list[str]`: Default: `[]`.
- `detail_ids: dict[str, list[str]]`: Default: `{}`.
- `assets: dict[str, AssetInfo]`: Default: `{}`.
- `asset_failures: list[str]`: Default: `[]`.
- `validators: dict[str, dict[str, str]]`: Default: `{}`.

## Public model helper functions

These helpers normalize provider values without downloading data.

### `localized_field`

```python
def localized_field(
    model: NanokaModel,
    locale: Locale | str,
    *keys: str,
    fallback: bool = True,
) -> str | None:
    ...
```

Select a model language field, then supplied fallback keys when enabled.

Return sanitized text or None; locale aliases are accepted and invalid aliases
raise ValueError. This pure helper removes ruby annotations without IO.

### `sanitize_localized_text`

```python
def sanitize_localized_text(value: str | None) -> str | None:
    ...
```

Strip game markup (notably Japanese ruby annotations) for display.

### `parse_rarity`

```python
def parse_rarity(value: str | int | None) -> int | None:
    ...
```

Convert a provider rarity label or numeric value to stars, or None if unknown.

### `normalize_path`

```python
def normalize_path(value: str | None) -> str | None:
    ...
```

Convert a provider path codename to its display alias, preserving unknown names.

### `normalize_path_codename`

```python
def normalize_path_codename(value: str | None) -> str | None:
    ...
```

Convert a path display alias to its provider codename, preserving unknown names.

### `parse_element`

```python
def parse_element(value: str | None) -> str | None:
    ...
```

Lowercase/trim an element name, or return None for missing text.

### `unix_datetime`

```python
def unix_datetime(value: int | float | None) -> datetime | None:
    ...
```

Parse a Unix-seconds timestamp as UTC, or None for absent/out-of-range data.

### `parse_datetime`

```python
def parse_datetime(value: str | datetime | None) -> datetime | None:
    ...
```

Parse ISO/date text or a datetime into UTC, or None when missing/invalid.

Naive dates are interpreted as UTC; ISO Z and slash-separated dates are accepted.

### `as_utc`

```python
def as_utc(value: datetime | None = None) -> datetime:
    ...
```

Return the current UTC time, or normalize a supplied datetime to UTC.

Naive values are interpreted as UTC rather than the host local timezone.

### `snake_case`

```python
def snake_case(value: str) -> str:
    ...
```

Convert provider PascalCase keys into lowercase underscore-separated keys.

### `sum_optional`

```python
def sum_optional(*values: float | None) -> float | None:
    ...
```

Sum present values, retaining None when every value is absent.

## Locale

Import `Locale` directly from `hsr_cards`. Values are `Locale.EN` (`en`), `Locale.ZH` (`zh`), `Locale.JA` (`ja`), and `Locale.KO` (`ko`).
