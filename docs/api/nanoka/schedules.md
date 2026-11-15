# Nanoka: Schedules and bosses

Canonical provider modes are `maze` (MOC), `maze_extra` (PF), `maze_boss` (AS), and `maze_peak` (AA). Queries accept the aliases documented in their signatures/docstrings. They expose provider schedules and details; use the separate [floor-card service](../../guides/endgame.md) to render MOC/PF/AS mechanics.

Provider effective-date properties can fall back to deployment/test windows. Inspect `live_begins_at` and `live_ends_at`, or a floor card's authoritative `begins_at`/`ends_at`, when live timing matters. Reading AA data does not enable AA floor cards.

```python
from hsr_cards import NanokaClient

async def query():
    async with NanokaClient(include_assets=False) as client:
        schedules = await client.list_maze(mode="PF")
        for schedule in schedules:
            print(schedule.id, client.schedule_windows(schedule))
```

`get_endgame_payload()` preserves the original dict/list payload for consumers that need provider fields.

All async methods below belong to [NanokaClient](../nanoka-client.md).

## Methods

### `get_current_boss_stages`

```python
async def get_current_boss_stages(
    mode: str = 'maze_extra',
    *,
    refresh: bool = False,
) -> EndgameDetail | PeakDetail | None:
    ...
```

Return current-season detail/stages, or None if the season/detail is absent.

Default mode is PF; aliases are accepted. Refresh revalidates version/locale
data and invalid-mode/cache/transport/model failures propagate.

### `get_current_endgame`

```python
async def get_current_endgame(mode: str = 'maze', *, refresh: bool = False) -> EndgameSeason | None:
    ...
```

Return the current mode schedule with optional detail data, or None.

Selection follows get_current_maze. Missing detail remains None; refresh
revalidates version/locale data and invalid-mode/cache/transport errors propagate.

### `get_current_maze`

```python
async def get_current_maze(*, mode: str = 'maze', refresh: bool = False) -> MazeSchedule | None:
    ...
```

Select the current schedule using authoritative live windows, or None if empty.

Fallbacks preserve the nearest scheduled window then sequence IDs when undated;
AA keeps its highest-ID behavior. Mode aliases are accepted. Refresh revalidates
data; invalid modes and cache/transport/model errors propagate.

### `get_current_peak`

```python
async def get_current_peak(*, refresh: bool = False) -> PeakSchedule | None:
    ...
```

Return the highest-ID AA schedule, or None if the catalog is empty.

This preserves the undated AA fallback; it does not establish a live date.
Refresh revalidates data and catalog/model/transport failures propagate.

### `get_endgame_detail`

```python
async def get_endgame_detail(
    identifier: int | str,
    *,
    mode: str = 'maze',
    refresh: bool = False,
) -> EndgameDetail:
    ...
```

Load parsed detail data by numeric season ID and canonical mode or alias.

AA routes to peak detail data. Missing documents raise NanokaNotFoundError;
refresh revalidates version/locale data and invalid-mode/model/cache/transport
failures propagate. This data operation does not enable AA rendering.

### `get_endgame_payload`

```python
async def get_endgame_payload(
    identifier: int | str,
    *,
    mode: str = 'maze',
    refresh: bool = False,
) -> dict[str, Any] | list[Any]:
    ...
```

Return a season's original JSON fields using a canonical mode or alias.

Preserve parameter arrays/descriptions and list-shaped payloads for card
services. Refresh revalidates the active version and locale cache; missing
seasons raise NanokaNotFoundError, unknown modes raise ValueError.
This exposes AA data without enabling AA floor-card rendering.

### `get_latest_endgame_detail`

```python
async def get_latest_endgame_detail(
    mode: str = 'maze',
    *,
    refresh: bool = False,
) -> EndgameDetail | PeakDetail | None:
    ...
```

Return detail data for the highest published season ID, or None if empty.

Mode aliases are accepted; refresh revalidates data. Missing details and
invalid-mode/model/cache/transport failures propagate.

### `get_live_boss`

```python
async def get_live_boss(mode: str = 'maze_extra', *, refresh: bool = False) -> BossEncounter | None:
    ...
```

Resolve current-season boss identities, variants, waves, and stage data.

Default mode is PF (maze_extra); aliases are accepted. Return None without a
schedule, otherwise BossEncounter even if detail/boss data is absent. Refresh
revalidates version/locale data; cache/transport/model failures propagate.

### `get_maze`

```python
async def get_maze(
    identifier: int | str,
    *,
    mode: str = 'maze',
    refresh: bool = False,
) -> MazeSchedule | None:
    ...
```

Return a schedule by numeric ID in the requested canonical mode or alias, or None.

Refresh revalidates version/locale data; invalid modes and cache/transport/model
failures propagate. Details are not loaded.

### `get_next_boss`

```python
async def get_next_boss(mode: str = 'maze_extra', *, refresh: bool = False) -> BossEncounter | None:
    ...
```

Resolve next-season boss identities, variants, waves, and stage data.

Default mode is PF (maze_extra); aliases are accepted. Return None without a
successor, otherwise BossEncounter. Refresh revalidates version/locale data;
invalid-mode/cache/transport/model failures propagate.

### `get_next_boss_stages`

```python
async def get_next_boss_stages(
    mode: str = 'maze_extra',
    *,
    refresh: bool = False,
) -> EndgameDetail | PeakDetail | None:
    ...
```

Return next-season detail/stages, or None if the season/detail is absent.

Default mode is PF; aliases are accepted. Refresh revalidates version/locale
data and invalid-mode/cache/transport/model failures propagate.

### `get_next_endgame`

```python
async def get_next_endgame(mode: str = 'maze', *, refresh: bool = False) -> EndgameSeason | None:
    ...
```

Return the next mode schedule with optional detail data, or None.

Selection follows get_next_maze. Missing detail remains None; refresh
revalidates version/locale data and invalid-mode/cache/transport errors propagate.

### `get_next_maze`

```python
async def get_next_maze(
    *,
    mode: str = 'maze',
    after: MazeSchedule | None = None,
    refresh: bool = False,
) -> MazeSchedule | None:
    ...
```

Select the next published schedule after after or the current schedule.

Prefer subsequent live windows, then the next ID; test dates do not select
the next season. Return None when no successor exists. Mode aliases are
accepted; refresh revalidates data and cache/transport/model errors propagate.

### `get_next_peak`

```python
async def get_next_peak(*, refresh: bool = False) -> PeakSchedule | None:
    ...
```

Return a published AA successor, currently None under the highest-ID fallback.

No reliable AA date selection is added here. Refresh revalidates data and
catalog/model/transport failures propagate.

### `get_peak`

```python
async def get_peak(identifier: int | str, *, refresh: bool = False) -> PeakSchedule | None:
    ...
```

Return an AA schedule by numeric ID, or None if no peak matches.

Refresh revalidates data and catalog/model/transport failures propagate.

### `get_peak_detail`

```python
async def get_peak_detail(identifier: int | str, *, refresh: bool = False) -> PeakDetail:
    ...
```

Load AA peak detail data by numeric ID without enabling AA floor cards.

Refresh revalidates version/locale data. Missing documents raise
NanokaNotFoundError; invalid IDs/models and cache/transport failures propagate.

### `list_endgames`

```python
async def list_endgames(
    mode: str = 'maze',
    *,
    live: bool | None = None,
    include_future: bool = True,
    refresh: bool = False,
) -> list[EndgameSeason]:
    ...
```

Load schedules and optional details for a canonical mode or supported alias.

Accept live filtering and include_future=True; missing details stay None.
Return [] for no schedules. Refresh revalidates data; invalid modes raise
ValueError and cache/transport/model failures propagate. Undated AA schedules
retain their existing sequence semantics; this API does not render AA cards.

### `list_maze`

```python
async def list_maze(
    *,
    mode: str = 'maze',
    live: bool | None = None,
    include_future: bool = True,
    refresh: bool = False,
) -> list[MazeSchedule]:
    ...
```

List mode schedules in start-date/ID order, including future seasons by default.

Modes accept canonical names and MOC/PF/AS/AA aliases. live=None disables
filtering; include_future=False excludes dated future starts. AA remains
ID-ordered because it has no dependable date windows. Refresh revalidates
locale/version data; unknown modes and cache/transport/model failures propagate.

### `list_peaks`

```python
async def list_peaks(*, refresh: bool = False) -> list[PeakSchedule]:
    ...
```

List undated AA peak schedules in ascending ID order.

Refresh revalidates version/locale data. Missing/invalid required catalog and
transport failures propagate; this does not enable AA floor cards.

### `list_schedules`

```python
async def list_schedules(
    mode: str = 'maze',
    *,
    window: str = 'live',
    refresh: bool = False,
) -> list[MazeSchedule]:
    ...
```

List schedules ordered by the selected window.

`window='live'` uses `live_begin`/`live_end` and falls back to
test dates only when a season has no live window yet. `window='test'`
always uses `begin`/`end`.

### `schedule_windows`

```python
def schedule_windows(schedule: MazeSchedule) -> dict[str, datetime | None]:
    ...
```

Return both deployment/test and live windows for a season.
