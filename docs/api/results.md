# Results and image wrappers

Card functions return different shapes. Player challenge/calendar methods return PIL `Image.Image`; `notes(raw=True)` adds `NotesData`, and `tier_list(raw=True)` adds `TierListData`. Character/equipment methods return the wrappers below; endgame returns season collections, and batch methods collect successes/errors.

```python
from hsr_cards import get_current_endgame_card

async def render():
    season = await get_current_endgame_card("PF", floors=4)
    for floor in season.cards:
        print(floor.floor, floor.stage_id, floor.image.size)
        floor.save(f"pf-{season.season_id}-floor-{floor.floor}.png")
```

`InfoCardResult`, Light Cone/relic/item wrappers, and `EndgameFloorCard` forward `save()` and unresolved PIL attributes. `SkillsCardResult` exposes its image and rich payload explicitly. Results own no provider client. A cache path may be `None`, including cache hits or disabled rendered caching; `save()` can always write an explicit destination.

## Card results

### `InfoCardResult`

Rendered info card with optional cached-card metadata.

Fields:

- `image: Image.Image`: Required.
- `character: str`: Required.
- `version: str | Sequence[str]`: Required.
- `cache_path: Path | None`: Default: `None`.

#### `save`

```python
def save(*args, **kwargs):
    ...
```

Save the wrapped image with PIL.Image.save arguments.

The destination, format and encoder options are passed through unchanged;
filesystem and encoder exceptions propagate.

### `SkillsCardResult`

Rendered skills card plus rich-message table payloads.

`tables` remains the backwards-compatible 2D array list. `table_models`
adds labels and stable ids, while `sections` carries the same labels
shown on the card for direct use in Telegram rich messages.

Access image attributes through `.image`, for example `result.image.size`. This wrapper has no character/version metadata and does not forward arbitrary image attributes.

Fields:

- `image: Image.Image`: Rendered PIL image.
- `tables: list[list[list[str]]]`: Ordered legacy 2D tables.
- `dropdowns: dict[str, int]`: Display labels mapped to table indices.
- `table_models: list[SkillTable]`: Validated labeled tables with stable IDs.
- `sections: SkillSections`: Skill/eidolon/material key-value groups.

#### `save`

```python
def save(*args, **kwargs):
    ...
```

Forward destination/format/encoder arguments to PIL.Image.save; file and encoding errors propagate.

#### `to_json_dict`

```python
def to_json_dict() -> dict[str, object]:
    ...
```

Return JSON-compatible tables, dropdowns, labeled table models and sections, excluding the PIL image.

### `SkillTable`

One rich-message table with its section/dropdown label.

Fields:

- `label: str`: Required.
- `table_id: str`: Required.
- `rows: list[list[str]]`: Default: `[]`.

### `SkillSections`

Key/value groups used beside each table in rich messages.

Fields:

- `skills: dict[str, dict[str, str]]`: Default: `{}`.
- `eidolons: dict[str, dict[str, str]]`: Default: `{}`.
- `materials: dict[str, str]`: Default: `{}`.

### `LCInfoCardResult`

PIL-compatible Light Cone card with version and cache metadata.

Fields:

- `image: Image.Image`: Rendered PIL image.
- `light_cone: str`: Localized Light Cone name.
- `identifier: int`: Numeric Nanoka ID.
- `version: str | tuple[str, str]`: Selected build or comparison pair.
- `cache_path: Path | None`: Generated-cache path when available.
- `description: str`: Localized expanded S1-S5 effect.
- `stats: dict[str, int]`: Level-80 hp/atk/def base stats.

#### `save`

```python
def save(*args, **kwargs):
    ...
```

Save the wrapped image with PIL destination, format, and encoder options.



### `RelicInfoCardResult`

PIL-compatible relic card and its localized set/piece metadata.

Fields:

- `image: Image.Image`: Rendered PIL image.
- `relic_set: str`: Localized relic set name.
- `identifier: int`: Numeric Nanoka ID.
- `version: str | tuple[str, str]`: Selected build or comparison pair.
- `cache_path: Path | None`: Generated-cache path when available.
- `set_type: str`: Cavern/planar set category.
- `effects: dict[int, str]`: Piece count mapped to localized set effect.
- `parts: list[RelicPart]`: Ordered relic pieces.

#### `save`

```python
def save(*args, **kwargs):
    ...
```

Save the wrapped image with PIL destination, format, and encoder options.



### `ItemInfoCardResult`

PIL-compatible item card with localized descriptions and sources.

Fields:

- `image: Image.Image`: Rendered PIL image.
- `item: str`: Localized item name.
- `identifier: int`: Numeric Nanoka ID.
- `version: str | tuple[str, str]`: Selected build or comparison pair.
- `cache_path: Path | None`: Generated-cache path when available.
- `description: str`: Localized item description.
- `background: str`: Localized background text.
- `purpose: str`: Localized item purpose.
- `rarity: int | None`: Published rarity when available.
- `main_type: str`: Localized main item category.
- `sub_type: str`: Localized subcategory.
- `sources: list[str]`: Localized acquisition sources.

#### `save`

```python
def save(*args, **kwargs):
    ...
```

Save the wrapped image with PIL destination, format, and encoder options.



### `EndgameFloorCard`

One floor image with its source stage and optional rendered-cache path.

Fields:

- `image: Image.Image`: Required.
- `floor: int`: Required.
- `stage_id: int | None`: Default: `None`.
- `name: str | None`: Default: `None`.
- `cache_path: Path | None`: Default: `None`.

#### `save`

```python
def save(*args, **kwargs):
    ...
```

Save the image using the arguments accepted by PIL.Image.save.

### `EndgameCardResult`

A season's floor cards and authoritative live-window metadata.

`begins_at`/`ends_at` are authoritative live windows and stay `None` for an undated upcoming season.

Fields:

- `game_mode: GameMode`: Required.
- `season_id: int`: Required.
- `season_name: str`: Required.
- `version: str`: Required.
- `cards: list[EndgameFloorCard]`: Default: `[]`.
- `begins_at: datetime | None`: Default: `None`.
- `ends_at: datetime | None`: Default: `None`.
- `is_live: bool`: Default: `False`.
- `next_season_id: int | None`: Default: `None`.

#### `end`

```python
end: datetime | None
```

Return ends_at as the compatibility end alias, or None for an undated season.

#### `images`

```python
images: list[Image.Image]
```

Return floor images in the same order as cards without copying the PIL images.

#### `start`

```python
start: datetime | None
```

Return begins_at as the compatibility start alias, or None for an undated season.

### `BatchCardResult`

One character's outcome from a batch render.

Fields:

- `identifier: int | str`: Required.
- `result: InfoCardResult | 'SkillsCardResult' | None`: Default: `None`.
- `error: Exception | None`: Default: `None`.

#### `image`

```python
image: Image.Image | None
```

Return the rendered PIL image, or None when no result was produced.

#### `ok`

```python
ok: bool
```

Return True when this item has no stored exception, even if its result is absent.

### `BatchRenderResult`

Batch render summary; one failure never aborts the other characters.

Fields:

- `items: list[BatchCardResult]`: Default: `[]`.

#### `errors`

```python
errors: dict[int | str, Exception]
```

Return identifier-to-exception entries for failed characters.

#### `failed`

```python
failed: list[BatchCardResult]
```

Return outcomes with a stored exception, preserving input order.

#### `images`

```python
images: list[Image.Image]
```

Return successful PIL images, omitting absent results and preserving input order.

#### `succeeded`

```python
succeeded: list[BatchCardResult]
```

Return outcomes with no stored exception, preserving input order.

### `CurrencyWarResult`

A rendered run plus navigation across the run list.

Runs are ordered newest-first as the API returns them: ``next()`` walks to
older runs and ``prev()`` to newer ones.

`next()` and `prev()` return neighboring indices, or `None`; request another card using `await client.currency_war(index=...)`.

Fields:

- `image: Image.Image`: Rendered run image.
- `current: int`: Current normalized run index.
- `total: int`: Number of available runs.
- `all: list[CurrencyWarRun]`: Runs in provider order.
- `data: CurrencyWarData`: Validated response data.

#### `has_next`

```python
has_next: bool
```



#### `has_prev`

```python
has_prev: bool
```



#### `next`

```python
def next(index: Optional[int] = None) -> Optional[int]:
    ...
```



#### `prev`

```python
def prev(index: Optional[int] = None) -> Optional[int]:
    ...
```



#### `save`

```python
def save(path) -> None:
    ...
```



## Domain query wrappers

Nanoka query wrappers retain resolved provider models. Attribute lookup uses the summary first, then the detail when an attribute is absent on the summary. This does not trigger a request.

### `Character`

A resolved character summary with an optional character detail model.

Expose summary fields first, then missing detail fields, and retain the query
locale for display_name(). Constructing the wrapper performs no IO.

Fields:

- `summary: Any`: Catalog summary model.
- `detail: Any | None`: Detail model when requested; otherwise None.
- `locale: Locale`: Normalized display locale.

#### `display_name`

```python
def display_name(locale: Locale | str | None = None, *, fallback: bool = True) -> str | None:
    ...
```

Return the summary name for locale or this wrapper locale.

fallback=True permits other-language text. Return None when no text exists;
invalid locale aliases raise ValueError and the operation performs no IO.

### `LightCone`

A resolved light-cone summary with optional refinements and stat details.

Expose summary fields first, then missing detail fields, and retain the query
locale for display_name(). Constructing the wrapper performs no IO.

Fields:

- `summary: Any`: Catalog summary model.
- `detail: Any | None`: Detail model when requested; otherwise None.
- `locale: Locale`: Normalized display locale.

#### `display_name`

```python
def display_name(locale: Locale | str | None = None, *, fallback: bool = True) -> str | None:
    ...
```

Return the summary name for locale or this wrapper locale.

fallback=True permits other-language text. Return None when no text exists;
invalid locale aliases raise ValueError and the operation performs no IO.

### `RelicSet`

A resolved relic-set summary with optional piece and effect details.

Expose summary fields first, then missing detail fields, and retain the query
locale for display_name(). Constructing the wrapper performs no IO.

Fields:

- `summary: Any`: Catalog summary model.
- `detail: Any | None`: Detail model when requested; otherwise None.
- `locale: Locale`: Normalized display locale.

#### `display_name`

```python
def display_name(locale: Locale | str | None = None, *, fallback: bool = True) -> str | None:
    ...
```

Return the summary name for locale or this wrapper locale.

fallback=True permits other-language text. Return None when no text exists;
invalid locale aliases raise ValueError and the operation performs no IO.

### `Monster`

A resolved monster summary with optional base stats and variant details.

Expose summary fields first, then missing detail fields, and retain the query
locale for display_name(). Constructing the wrapper performs no IO.

Fields:

- `summary: Any`: Catalog summary model.
- `detail: Any | None`: Detail model when requested; otherwise None.
- `locale: Locale`: Normalized display locale.

#### `display_name`

```python
def display_name(locale: Locale | str | None = None, *, fallback: bool = True) -> str | None:
    ...
```

Return the summary name for locale or this wrapper locale.

fallback=True permits other-language text. Return None when no text exists;
invalid locale aliases raise ValueError and the operation performs no IO.

## Schedule wrappers

These SDK objects expose effective dates that can fall back to test/deployment windows. Use explicit schedule `live_begins_at`/`live_ends_at` or a rendered season authoritative live dates for current/next decisions.

### `BossEncounter`

Resolved endgame boss data for one stage (card-generator friendly).

Fields:

- `mode: str`: Required.
- `season: MazeSchedule`: Required.
- `stage: StageLevel | None`: Default: `None`.
- `detail: EndgameDetail | PeakDetail | None`: Default: `None`.
- `bosses: list[Monster]`: Default: `[]`.
- `waves: list[StageEvent]`: Default: `[]`.
- `monster_ids: list[int]`: Default: `[]`.
- `locale: Locale`: Default: `Locale.EN`.

#### `boss`

```python
boss: Monster | None
```

Return the first resolved boss, or None when no bosses were resolved.

#### `boss_names`

```python
boss_names: list[str]
```

Return boss names in the encounter locale, falling back to numeric IDs.

#### `boss_names_for`

```python
def boss_names_for(locale: Locale | str | None = None, *, fallback: bool = True) -> list[str]:
    ...
```

Return localized boss names, falling back to IDs when names are missing.

Locale defaults to the encounter locale; fallback=True accepts other-language
text. Invalid locale aliases raise ValueError; this performs no IO.

#### `ends_at`

```python
ends_at: datetime | None
```

Return the detail/schedule effective UTC end, or None when no date exists.

#### `id`

```python
id: int
```

Return the published season/schedule ID.

#### `mode_label`

```python
mode_label: str
```

Return the display label for the canonical mode.

#### `name`

```python
name: str | None
```

Return the schedule display name, or None when no localized name is present.

#### `stage_name`

```python
stage_name: str | None
```

Return the resolved stage name, or None if the stage is absent.

#### `starts_at`

```python
starts_at: datetime | None
```

Return the detail UTC start, falling back to the effective schedule start.

#### `version`

```python
version: str | None
```

Return the published schedule build version, or None when unknown.

### `EndgameSeason`

A mode-specific schedule plus its detail document.

Fields:

- `mode: str`: Required.
- `schedule: MazeSchedule`: Required.
- `detail: EndgameDetail | PeakDetail | None`: Default: `None`.

#### `begins_at`

```python
begins_at: datetime | None
```

Return the schedule live UTC start, falling back to the test start.

#### `boss_ids`

```python
boss_ids: list[int]
```

Return published detail boss IDs, or [] if detail data is absent.

#### `boss_names`

```python
boss_names: list[str]
```

Return the AA peak boss name, or [] for other modes or absent peak data.

#### `ends_at`

```python
ends_at: datetime | None
```

Return the detail/schedule effective UTC end, or None when no date exists.

#### `id`

```python
id: int
```

Return the published season/schedule ID.

#### `is_live`

```python
is_live: bool
```

Return schedule live status; undated schedules retain the existing True fallback.

#### `name`

```python
name: str | None
```

Return the schedule display name, or None when no localized name is present.

See [Nanoka model fields](nanoka-models.md), [HoYoLAB models](hoyolab-models.md), and [Prydwen models](prydwen-models.md).
