# HonkaiStarrail

The convenience facade renders cards through independent HoYoLAB, Nanoka, and Prydwen clients. Import it with `from hsr_cards import HonkaiStarrail`. Only player operations require a supported UID and credentials.

```python
from hsr_cards import HonkaiStarrail

async def render():
    async with HonkaiStarrail() as client:
        result = await client.get_character_info(1507, version="4.7.51")
        result.save("character.png")
```

Construction and context entry perform no requests. `await close()` and the async context close only clients created by this facade. Injected clients remain caller-owned. For complete examples, use the [quickstart](../getting-started/quickstart.md), [player guide](../guides/player-cards.md), or [showcase](../showcase.md). The [result reference](results.md) lists the returned properties.

`GameMode` is `Literal["MOC", "PF", "AS", "AA"]` for current/next floor cards; AA rendering is deferred. The standalone [card functions](card-functions.md) expose `force_refresh` for character/equipment cards in addition to the facade options.

## Constructor

```python
def __init__(
    uid: int | str | None = None,
    cookie: Cookies | None = None,
    proxy: str | None = None,
    *,
    hoyolab_client: HoYoLABClient | None = None,
    nanoka_client: NanokaClient | None = None,
    prydwen_client: PrydwenClient | None = None,
):
    ...
```

Store optional player settings and independently borrowed provider clients.

Existing positional uid/cookie/proxy arguments retain their meaning.
Omitting UID supports catalog, build, tier, and non-player card methods.
No network session is opened until an operation needs one.

## Configuration fields

These fields describe the configured instance. Use constructor options to set them.

- `uid: str | None`: Optional player UID, stored as text. An injected HoYoLAB client can supply it.
- `cookie: Cookies | None`: Explicit player credentials, or borrowed HoYoLAB credentials.
- `proxy: str | None`: Default proxy for delegated provider requests.

## Provider properties

### `hoyolab`

```python
hoyolab: HoYoLABClient
```

Return the player query client; missing UID raises ValueError before IO.

### `nanoka`

```python
nanoka: NanokaClient
```

Return the lazy Nanoka domain client with its standard asset-cache settings.

### `prydwen`

```python
prydwen: PrydwenClient
```

Return the lazy Prydwen client; it never constructs a HoYoLAB API.

### `api`

```python
api: BaseAPI
```

Expose the HoYoLAB API for legacy integrations; accessing it requires UID.

This property also accepts assignment. Install a borrowed HoYoLAB API without opening it or transferring ownership.

Replacing an internally owned API with an open session raises RuntimeError;
close that API first so replacing it cannot leak its session.

## Non-player character and equipment cards

### `get_character_info`

```python
async def get_character_info(
    identifier: int | str,
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
) -> InfoCardResult:
    ...
```

Render a Nanoka character info card for this client's locale.

`version` follows Nanoka's rules: omit it for the newest published
build, pass one build for a pinned card, or pass `(from, to)` for a
comparison card. identifier accepts a numeric ID or published name;
locale selects Nanoka's language (default en), cache_dir overrides provider
data, and rendered_cache_dir overrides generated images. proxy overrides
the facade proxy. use_rendered_cache=False disables image-cache IO.

Return InfoCardResult (image, character, version, cache_path); loading,
invalid identifiers/versions, and rendering errors propagate. No player
data or credentials are accessed.

### `get_character_skills`

```python
async def get_character_skills(
    identifier: int | str,
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
) -> SkillsCardResult:
    ...
```

Render a character skills/eidolon sheet and rich-message tables. Identifier, version, locale, proxy, and cache rules match `get_character_info()`. The result contains `image`, `tables`, `dropdowns`, `table_models`, and `sections`; use `to_json_dict()` for the JSON payload. It carries no character/version fields. Paired versions compare changes inline. Provider and rendering errors propagate.

### `get_LC_info`

```python
async def get_LC_info(
    identifier: int | str,
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
) -> LCInfoCardResult:
    ...
```

Render a level-80 Light Cone card with all S1-S5 values inline.

Arguments and version comparisons follow get_character_info().

### `get_relic_info`

```python
async def get_relic_info(
    identifier: int | str,
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
) -> RelicInfoCardResult:
    ...
```

Render relic set bonuses and every piece, including planar sets.

Arguments and version comparisons follow get_character_info().

### `get_item_info`

```python
async def get_item_info(
    identifier: int | str,
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
) -> ItemInfoCardResult:
    ...
```

Render a Nanoka item card with its description and sources.

Arguments and version comparisons follow get_character_info().

### `render_all_info`

```python
async def render_all_info(
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
    concurrency: int = 4,
    include_beta: bool = True,
    identifiers: list[int | str] | tuple[int | str, ...] | None = None,
) -> BatchRenderResult:
    ...
```

Render the selected character catalog with bounded concurrency and return `BatchRenderResult`. Supply `identifiers` to render a subset. Versions support the same single/comparison forms as `get_character_info()`. Each render bypasses the image cache and replaces matching files when caching is enabled. Ordinary per-character errors are collected; cancellation propagates.

### `render_all_skills`

```python
async def render_all_skills(
    version: str | tuple[str, str] | list[str] | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
    concurrency: int = 4,
    include_beta: bool = True,
    identifiers: list[int | str] | tuple[int | str, ...] | None = None,
) -> BatchRenderResult:
    ...
```

Render skills/eidolon sheets for the selected catalog and return `BatchRenderResult`. Selection, comparison versions, concurrency, replacement of cached images, and per-item error handling follow `render_all_info()`. Cancellation propagates.

## Endgame floor cards

### `get_current_endgame_card`

```python
async def get_current_endgame_card(
    game_mode: GameMode = 'MOC',
    floors: list[int] | tuple[int, ...] | int | None = None,
    *,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> EndgameCardResult:
    ...
```

Render one Telegram-friendly info card per requested live endgame floor.

MOC defaults to floors 11 and 12; PF and AS default to 3 and 4.
AA cards are deferred and raise `NotImplementedError`. floors accepts
one number or a sequence. Return EndgameCardResult with ordered floor
cards; absent live seasons/invalid floors raise ValueError.

locale/cache/proxy options configure operation-owned clients; an injected
Nanoka client retains its settings and lifecycle. force_refresh bypasses
image-cache reads; use_rendered_cache=False disables image-cache IO.

### `get_next_endgame_card`

```python
async def get_next_endgame_card(
    game_mode: GameMode = 'MOC',
    floors: list[int] | tuple[int, ...] | int | None = None,
    *,
    look_ahead: int | Literal['max'] = 1,
    locale: str = 'en',
    cache_dir: str | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> EndgameCardResult | list[EndgameCardResult]:
    ...
```

Render upcoming MOC/PF/AS floor cards. `look_ahead=1` returns one `EndgameCardResult` and raises `ValueError` if no upcoming season resolves. Larger positive integers and `"max"` return an ordered list, which may be empty. MOC defaults to floors 11/12; PF and AS default to 3/4. Undated upcoming seasons show `UNSCHEDULED` and have `None` live dates. Cache, locale, proxy, and injected-client ownership follow `get_current_endgame_card()`. AA raises `NotImplementedError`.

## Player challenge cards

### `MOC`

```python
async def MOC(schedule_type: Literal['1', '2'] = '1') -> Image.Image:
    ...
```

Render current (1) or previous (2) player MOC floors as a PIL image.

### `PF`

```python
async def PF(schedule_type: Literal['1', '2'] = '1') -> Image.Image:
    ...
```

Render current (1) or previous (2) player PF floors as a PIL image.

### `shadow`

```python
async def shadow(schedule_type: Literal['1', '2'] = '1') -> Image.Image:
    ...
```

Render current (1) or previous (2) player AS floors as a PIL image.

### `anomaly`

```python
async def anomaly() -> Image.Image:
    ...
```

Render the player AA record; API or rendering errors raise HSR_Error.

## Calendar and player state

### `banners`

```python
async def banners() -> Image.Image:
    ...
```

Render calendar banners as a PIL image; failures raise HSR_Error.

### `events`

```python
async def events() -> Image.Image:
    ...
```

Render personalized calendar events when explicit cookies are supplied.

### `endgame`

```python
async def endgame() -> Image.Image:
    ...
```

Render the HoYoLAB schedule calendar as a PIL image.

### `notes`

```python
async def notes(raw: bool = False) -> Image.Image | tuple[Image.Image, NotesData]:
    ...
```

Render authenticated daily notes; raw=True also returns validated NotesData.

### `currency_war`

```python
async def currency_war(
    index: int = 0,
    raw: bool = False,
) -> CurrencyWarResult | tuple[CurrencyWarResult, CurrencyWarData]:
    ...
```

Render one Currency Wars run.

`index` follows the API order (0 is the most recent run) and accepts
negative values. The result exposes `image`, `current`, `next()`,
`prev()` and `all` for paging through the recent runs. raw=True
additionally returns validated CurrencyWarData. API/render errors,
including an unavailable run index, are wrapped in HSR_Error.

### `verify_cookies`

```python
async def verify_cookies() -> bool:
    ...
```

Check explicit HoYoLAB cookies; absent cookies or request errors return False.

## Prydwen and community builds

### `character_build`

```python
async def character_build(
    identifier: int | str | None = None,
    url: bool = False,
    *,
    detailed: bool = False,
    name: str | None = None,
    element: str | None = None,
    path: str | None = None,
    rarity: int | None = None,
    released: bool | None = None,
    include_beta: bool = True,
    search: str | None = None,
    build_dir: str | Path | None = None,
    **filters: Any,
) -> Image.Image | str | list[Image.Image] | list[str] | None:
    ...
```

Return a clean build image/link or detailed summary plus condition pages.

Identifiers/filters follow Nanoka's catalog rules. Missing variants return
None. build_dir overrides local build assets; provider errors propagate.
Installed packages download cards with `update_builds()` before lookup.
An existing Nanoka client stays caller/facade-owned; otherwise a temporary
client loads catalogs without bulk assets and is closed on completion.

### `tier_list`

```python
async def tier_list(
    game_mode: Literal['MOC', 'PF', 'AS'] = 'MOC',
    raw: bool = False,
    *,
    timeout: float = 30.0,
) -> Image.Image | tuple[Image.Image, TierListData]:
    ...
```

Render a Prydwen MOC/PF/AS tier list, optionally with its parsed data.

The default is MOC. timeout controls public HTTP/image requests and this
facade's proxy applies to Prydwen. This call needs no player UID/cookies;
provider/render errors raise HSR_Error. The renderer owns its session.

### `redeem_codes`

```python
async def redeem_codes() -> list[RedeemCode]:
    ...
```

Fetch active HSR redeem codes and rewards through the Prydwen client.

Makes a public HTTP request without player credentials. Failures are
wrapped in HSR_Error; an empty provider list remains an empty list.

### `update_builds`

```python
async def update_builds(
    *,
    metadata_url: str = 'https://raw.githubusercontent.com/MR-LORD-REX/hsr-cards/main/src/hsr_cards/assets/char_builds/metadata.json',
    build_dir: str | Path | None = None,
) -> int:
    ...
```

Download all indexed community build images; return the image count.

metadata_url selects the GitHub manifest. build_dir overrides the local
destination: existing source-checkout build assets or `.hsr_cards_builds`
under the working directory for an installed package. Missing directories
are created on download. Own the temporary public-download session; no
player UID/cookies are required. Invalid metadata or download errors raise
HSR_Error. Local-only cards and previous metadata survive failed updates.

## Cache and lifecycle

### `update_nanoka_assets`

```python
async def update_nanoka_assets(*, version: str | None = None, force: bool = False) -> None:
    ...
```

Refresh Nanoka data/assets, optionally selecting a published build.

force revalidates the active cache. Invalid versions and provider/cache
failures propagate. Injected Nanoka clients retain their settings/lifecycle.

### `close`

```python
async def close() -> None:
    ...
```

Release owned clients only; unused and caller-supplied clients stay untouched.

All owned clients are given a chance to close if one cleanup fails. The
first failure is re-raised after cleanup; repeated successful calls are safe.
