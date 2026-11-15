# Standalone card and tier functions

These functions are exported directly by `hsr_cards` and need no player UID/cookies. Await asynchronous renders; `parse_tier_list()` is synchronous. They return image wrappers, season/batch collections, or tier models as described below.

```python
from hsr_cards import get_character_info, get_character_skills

async def render():
    info = await get_character_info(1507, version="4.7.51")
    info.save("info.png")
    skills = await get_character_skills(1507, version="4.7.51")
    skills.save("skills.png")
    payload = skills.to_json_dict()
    print(payload.keys())
```

Character/equipment `version` accepts `None` (latest), one build string, or a two-item `(older, newer)` comparison; more than two values raises `ValueError`. Locale defaults to English. `force_refresh=True` bypasses rendered-image reads; `use_rendered_cache=False` disables their read/write IO. Provider catalogs/assets can still be requested/cached. Operation-created clients are closed even when loading fails.

Current/next `game_mode` uses `GameMode = Literal["MOC", "PF", "AS", "AA"]`; runtime strings strip whitespace and normalize uppercase. MOC default floors are 11/12; PF/AS are 3/4. AA floor cards raise `NotImplementedError`. An initialized `client=` is borrowed, and its language controls cache locale. Next requests with `look_ahead=1` return one season or raise; larger counts/`"max"` return a list, possibly empty. Undated upcoming results retain `None` live dates.

For worked selections, see [characters](../guides/characters.md), [endgame](../guides/endgame.md), [batch/cache behavior](../guides/caching.md), and [results](results.md). [Demo outputs](../showcase.md) show the rendered methods.

## Functions

### `get_character_info`

```python
async def get_character_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> InfoCardResult:
    ...
```

Render one character detail card or an inline version comparison.

identifier accepts a numeric Nanoka ID or published character name. version=None
selects the newest published build; a string pins one build, and a two-item
sequence supplies (older, newer). More than two versions raises ValueError.
locale defaults to en and accepts Nanoka locale aliases. cache_dir selects the
downloaded-data root, proxy configures provider requests, and rendered_cache_dir
selects the generated-image root (default .hsr_cards_rendered in the caller's cwd).

Return InfoCardResult with image, resolved character name/version and an optional
path for newly saved images. use_rendered_cache=False disables image-cache IO;
force_refresh bypasses image-cache reads. Loading may still request/cache provider
data. Unknown characters, invalid data and provider/render/file errors propagate.
All Nanoka clients created by this operation are closed, including on failure.

### `get_character_skills`

```python
async def get_character_skills(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> SkillsCardResult:
    ...
```

Render the full skills/eidolon sheet and its rich-message payloads.

identifier accepts a Nanoka ID or published name. version=None selects the newest
build, a string pins one build, and (older, newer) compares two builds inline.
Invalid version-sequence lengths raise ValueError. locale defaults to en;
cache_dir/proxy configure provider data, while rendered_cache_dir defaults to
.hsr_cards_rendered in the caller's cwd.

Return SkillsCardResult containing image, tables, label-to-table dropdown indices,
labeled table_models and skills/eidolons/materials sections. Payloads are rebuilt
even when the image is cached. force_refresh bypasses image-cache reads;
use_rendered_cache=False disables image-cache IO. Provider/model/render errors
propagate, and operation-created clients are always closed.

### `get_LC_info`

```python
async def get_LC_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> LCInfoCardResult:
    ...
```

Render a level-80 Light Cone with inline S1-S5 effect values.

Arguments and single/comparison version semantics match get_character_info.

### `get_relic_info`

```python
async def get_relic_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> RelicInfoCardResult:
    ...
```

Render set bonuses and all pieces, using the get_character_info arguments.

### `get_item_info`

```python
async def get_item_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> ItemInfoCardResult:
    ...
```

Render an inventory item, using the get_character_info arguments.

### `get_current_endgame_card`

```python
async def get_current_endgame_card(
    game_mode: GameMode = 'MOC',
    floors: Sequence[int] | int | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
    client: NanokaClient | None = None,
) -> EndgameCardResult:
    ...
```

Render live MOC/PF/AS floor cards, one image per requested floor.

game_mode accepts the suggested mode codes case-insensitively with whitespace
trimmed. AA raises NotImplementedError until live schedules are reliable. floors
is one integer or a sequence; None selects MOC 11/12 or PF/AS 3/4. Requested
floors are deduplicated and sorted.

Return EndgameCardResult with ordered floor cards, resolved provider version and
authoritative live-window metadata. Missing live/stage data or absent floors
raises ValueError; unsupported modes/locales and provider/render/file failures
propagate. No player credentials or records are requested.

locale defaults to en; cache_dir/proxy configure an internally created Nanoka
client. An initialized client may be injected and stays caller-owned: its
language overrides locale, including the rendered-cache suffix, and its cache/
proxy settings remain active. Otherwise one operation-owned client is initialized,
reused for all floors and closed even on failure.

rendered_cache_dir defaults to .hsr_cards_rendered under the caller cwd.
force_refresh bypasses generated-image reads; use_rendered_cache=False disables
generated-image IO. Catalog/assets may still be requested and cached.

### `get_next_endgame_card`

```python
async def get_next_endgame_card(
    game_mode: GameMode = 'MOC',
    floors: Sequence[int] | int | None = None,
    *,
    look_ahead: int | Literal['max'] = 1,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
    client: NanokaClient | None = None,
) -> EndgameCardResult | list[EndgameCardResult]:
    ...
```

Render upcoming MOC/PF/AS floor cards after the latest started live cycle.

game_mode accepts trimmed, case-insensitive mode codes; AA raises
NotImplementedError. floors accepts one integer or a sequence; None selects
MOC 11/12 or PF/AS 3/4, sorted and deduplicated. look_ahead defaults to one;
positive larger values or "max" request multiple successfully resolved seasons.

Return one EndgameCardResult for look_ahead=1, otherwise a list ordered by live
start time. Undated published seasons follow dated ones with UNSCHEDULED status
and absent live dates. Missing/unrenderable seasons are skipped; an empty single
request raises ValueError, while list requests may return []. Invalid mode,
locale/look-ahead or provider/render/file failures propagate.

locale defaults to en and cache_dir/proxy configure operation-created clients.
An initialized injected client keeps its settings and ownership; its language
overrides locale, including generated-image cache suffixes. Otherwise one client
is initialized, reused across all seasons and closed even on failure.
rendered_cache_dir defaults to the caller-relative .hsr_cards_rendered directory.
force_refresh bypasses generated-image reads; use_rendered_cache=False disables
generated-image IO. Provider catalogs/assets may still be requested and cached.

### `render_all_info`

```python
async def render_all_info(
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    concurrency: int = 4,
    include_beta: bool = True,
    identifiers: Sequence[int | str] | None = None,
) -> BatchRenderResult:
    ...
```

Rerender character info cards concurrently and collect every outcome.

version accepts newest (None), pinned (string), or (older, newer) comparison builds.
identifiers optionally limits the batch to IDs/names, removing duplicates while
preserving order. Otherwise the catalog is listed with include_beta=True by
default. concurrency defaults to four and is clamped to at least one worker.
locale defaults to en; cache_dir/proxy configure Nanoka data and requests;
rendered_cache_dir selects generated images in the caller-relative cache root.

Return BatchRenderResult in input order. Each card forces a fresh image and
replaces its cache file unless use_rendered_cache=False. Per-character Exceptions
are stored rather than aborting siblings; cancellation propagates. Catalog/version
failures propagate before rendering. Listing and render clients are operation-owned
and closed by their respective services.

### `render_all_skills`

```python
async def render_all_skills(
    version: str | Sequence[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    concurrency: int = 4,
    include_beta: bool = True,
    identifiers: Sequence[int | str] | None = None,
) -> BatchRenderResult:
    ...
```

Rerender character skills/eidolon sheets concurrently and collect outcomes.

version accepts newest (None), pinned (string), or ordered comparison builds.
identifiers limits the catalog to IDs/names; otherwise include_beta controls
unreleased entries. concurrency defaults to four, with a minimum of one worker.
locale/cache_dir/proxy/rendered_cache_dir have the same meanings as
get_character_skills(); use_rendered_cache=False disables generated-image IO.

Return BatchRenderResult in input order. Cached images are always replaced by
fresh renders. Per-character Exceptions are stored; cancellation and catalog
failures propagate. Every service closes the provider clients it creates.

### `tier_list`

```python
async def tier_list(
    game_mode: GameMode = 'MOC',
    *,
    raw: bool = False,
    timeout: float = 30.0,
    proxy: str | None = None,
) -> Image.Image | tuple[Image.Image, TierListData]:
    ...
```

Render Prydwen's MOC, PF, or AS list; `raw=True` also returns its data.

This standalone entry point requires no player UID or HoYoLAB cookies.

### `fetch_tier_list`

```python
async def fetch_tier_list(
    url: str = 'https://www.prydwen.gg/star-rail/tier-list',
    *,
    game_mode: GameMode = 'MOC',
    timeout: float = 30.0,
    proxy: str | None = None,
) -> TierListData:
    ...
```

Fetch MOC/PF/AS rankings as TierListData with source and update metadata.

url defaults to the public tier page. game_mode aliases are case-insensitive;
timeout is positive seconds and proxy applies to both HTTP and HTTPS.
Runs HTTP in a worker and closes its scraper. Invalid input/missing rankings
raise ValueError; request/dependency errors propagate. No files are written.

### `parse_tier_list`

```python
def parse_tier_list(
    html: str,
    *,
    game_mode: GameMode = 'MOC',
    source: str = 'https://www.prydwen.gg/star-rail/tier-list',
) -> TierListData:
    ...
```

Parse MOC, PF, or AS rankings from Prydwen's HTML and embedded data.

Plain HTML without embedded ratings is supported only when its visible
tier list matches the requested mode; it never substitutes another mode.
game_mode defaults to MOC and accepts case-insensitive aliases. source is
retained as provenance and resolves relative portraits. Returns TierListData;
invalid modes, absent rankings, and malformed hydrated data raise ValueError.
Performs no requests or filesystem operations.
