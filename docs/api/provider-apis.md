# Provider APIs

Provider APIs expose transport and original payload access. Use the [domain clients](nanoka-client.md) for filtered, typed queries and [HonkaiStarrail](main-client.md) for images. All providers preserve ownership of injected resources.

## Imports

```python
from hsr_cards.providers.hoyolab.api import BaseAPI
from hsr_cards.providers.nanoka.api import NanokaAPIClient
from hsr_cards.providers.prydwen.api import PrydwenAPIClient
```

## NanokaAPIClient

Raw version/locale-aware Nanoka JSON and cached artwork. `detail()` uses canonical kinds; `document()` accepts a cache-relative JSON path. Construction is offline.

```python
def __init__(
    *,
    version: str | None = None,
    language: Locale | str = Locale.EN,
    cache_dir: str | Path | None = None,
    base_url: str = 'https://static.nanoka.cc/hsr',
    asset_base_url: str = 'https://static.nanoka.cc/assets/hsr',
    proxy: str | None = None,
    timeout: float = 30.0,
    retries: int = 3,
    include_assets: bool = True,
    auto_update: bool = False,
    concurrency: int = 16,
    cache: NanokaCache | None = None,
    http: AsyncHTTP | None = None,
):
    ...
```

Configure raw data access without downloading files or opening a session.

version=None resolves the newest build on first initialization; language
accepts Locale aliases. cache_dir defaults to caller-relative .nanoka_cache.
HTTP uses the configured bases, proxy, 30-second timeout, three retries,
and bounded concurrency. include_assets controls bulk asset downloads;
auto_update revalidates on cache access. Injected cache settings take
precedence over constructor settings. An injected HTTP/cache remains
caller-owned; otherwise this client closes the resources it creates.
Invalid language aliases raise ValueError.

- `version: str | None`: Active selected build.
- `language: Locale`: Normalized locale.
- `cache_dir: Path`: Downloaded cache root.
- `base_url: str`: Catalog CDN base.
- `asset_base_url: str`: Artwork CDN base.
- `include_assets: bool`: Bulk asset initialization setting.
- `auto_update: bool`: Automatic revalidation setting.

### `cache`

```python
cache: NanokaCache
```

Return the configured cache; reading this property performs no IO.

### `cache_path`

```python
cache_path: Path
```

Return the active version/locale directory without creating it.

### `catalog`

```python
async def catalog(filename: str, *, required: bool = True) -> dict[str, Any]:
    ...
```

Load a cache-relative catalog document for this version and locale.

Return a mapping, or {} for an absent optional or non-mapping document.
required=True raises NanokaCacheError for a missing file. Missing cache data is
initialized asynchronously and the resolved version is synchronized.

### `clear_cache`

```python
async def clear_cache(*, version: str | None = None) -> None:
    ...
```

Remove one cached build, or all version trees/global metadata when omitted.

Deletion is scoped to the configured cache root; active-build metadata is
invalidated so later access can initialize it again. This performs file IO.

### `close`

```python
async def close() -> None:
    ...
```

Close only cache and HTTP resources created by this API client.

Injected resources remain caller-owned; await this on the owning event loop.

### `detail`

```python
async def detail(
    kind: str,
    identifier: int | str,
    *,
    required: bool = True,
    refresh: bool = False,
) -> dict[str, Any] | list[Any] | None:
    ...
```

Load an original detail document by canonical kind and numeric ID.

Return dict/list JSON, or None when absent and required=False; required=True
raises NanokaNotFoundError. Unknown kinds raise KeyError. refresh=True
revalidates the version/locale cache; cache and transport failures propagate.

### `document`

```python
async def document(relative_path: str, *, required: bool = True) -> Any | None:
    ...
```

Read original JSON from a cache-relative path for this version/locale.

Preserve list/mapping/scalar payloads. Return None for an absent optional
document; missing required or malformed files raise NanokaCacheError.
Missing cache data is initialized asynchronously, which may download/write
files. Synchronize the resolved version; cache/transport failures propagate.

### `fetch_asset`

```python
async def fetch_asset(relative: str, *, refresh: bool = False) -> Path | None:
    ...
```

Cache a CDN-relative asset and return its path, or None if unavailable.

Refresh revalidates the build first. Missing/invalid asset responses return
None; cache initialization and transport errors propagate.

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

Return an unmodified season document for a canonical mode or alias.

Version and locale belong to this client. Refresh revalidates its cache;
missing seasons raise NanokaNotFoundError, unknown modes raise ValueError.
AA data access does not enable AA cards. Dict/list payloads keep all fields.

### `get_versions`

```python
async def get_versions(*, refresh: bool = False) -> NanokaVersions:
    ...
```

Return the builds currently published by Nanoka.

`live_server` is the stable game build (for example `4.7`) and
`live_beta` is the newest published patch build (for example
`4.7.51`). `versions` contains every selectable build.
refresh=True replaces cached global metadata when the CDN is available;
otherwise existing complete cache metadata may be used. Network/file
writes are possible and cache/transport failures propagate.

### `initialize`

```python
async def initialize(*, force: bool = False) -> NanokaAPIClient:
    ...
```

Ensure catalogs and optional assets for the configured version/locale.

force=True refreshes cached data. Return this client after resolving its version;
network and NanokaCacheError failures propagate. Construction itself stays offline.

### `prepare`

```python
async def prepare(refresh: bool = False) -> None:
    ...
```

Initialize missing data, or revalidate catalogs when refresh=True.

Synchronize the active version after cache discovery. This may perform network
requests and write cache files; transport/cache errors propagate.

### `update_assets`

```python
async def update_assets(*, version: str | None = None, force: bool = False) -> NanokaAPIClient:
    ...
```

Revalidate/download one published build, or the active build.

Passing `version` also switches the client to that build, so a
subsequent card render reads the assets that were just refreshed.
Unknown published versions raise ValueError before switching. force=True
replaces cached data; cache/transport failures propagate. Return this
API client after synchronizing the active version.

## BaseAPI

Raw HoYoLAB player transport. `cookie` is a mapping; use `Cookies.model_dump()` to convert the public credential model. Fetches return provider JSON, and transport failures may become an empty dict. Domain queries apply validation/error handling. UID/server and endpoint access can validate credentials/configuration. Borrowed sessions stay caller-owned.

```python
def __init__(
    uid: int | str,
    cookie: Mapping[str, str] | None = None,
    proxy: str | None = None,
    *,
    session: aiohttp.ClientSession | None = None,
):
    ...
```

Store request configuration; no HTTP, credential lookup, or file IO occurs.

- `uid: str`: Configured player UID.
- `cookie: Mapping[str, str] | None`: Explicit credential mapping.
- `proxy: str | None`: Request proxy.
- `server: Server`: Resolved supported player region.

### `close`

```python
async def close() -> None:
    ...
```

Close only the session created by this API; repeated calls are harmless.

### `endpoints`

```python
endpoints: BaseEndpoint
```

Resolve request headers from explicit cookies or configured environment values.

This property also accepts assignment. Replace endpoint configuration, for example for an injected test transport.

### `fetch_anomaly`

```python
async def fetch_anomaly(
    schedule_type: Literal['1'] = '1',
    server: Server = 'prod_official_asia',
    need_all: NeedAll = 'false',
) -> dict[str, Any]:
    ...
```

Fetch AA player records; return raw JSON or an empty dict on transport failure.

### `fetch_as`

```python
async def fetch_as(
    schedule_type: Schedule = '1',
    server: Server = 'prod_official_asia',
    need_all: NeedAll = 'false',
) -> dict[str, Any]:
    ...
```

Fetch current (1) or previous (2) Apocalyptic Shadow player records as raw JSON.

### `fetch_calendar`

```python
async def fetch_calendar(server: Server = 'prod_official_asia') -> dict[str, Any]:
    ...
```

Fetch the personalized or configured public calendar without rendering it.

Explicit cookies use this API's UID/server. The public mode retains the
configured default UID and Asia server. Missing configuration raises
ValueError; network failures return an empty dict.

### `fetch_currency_war`

```python
async def fetch_currency_war(server: Server = 'prod_official_asia') -> dict[str, Any]:
    ...
```

Fetch recent Currency Wars player runs; transport failures return an empty dict.

### `fetch_moc`

```python
async def fetch_moc(
    schedule_type: Schedule = '1',
    server: Server = 'prod_official_asia',
    need_all: NeedAll = 'false',
) -> dict[str, Any]:
    ...
```

Fetch current (1) or previous (2) Memory of Chaos player records as raw JSON.

### `fetch_notes`

```python
async def fetch_notes(server: Server = 'prod_official_asia') -> dict[str, Any]:
    ...
```

Fetch authenticated daily notes; transport failures return an empty dict.

### `fetch_pf`

```python
async def fetch_pf(
    schedule_type: Schedule = '1',
    server: Server = 'prod_official_asia',
    need_all: NeedAll = 'false',
) -> dict[str, Any]:
    ...
```

Fetch current (1) or previous (2) Pure Fiction player records as raw JSON.

### `session`

```python
session: aiohttp.ClientSession
```

Return the borrowed session or lazily create an internally owned session.

Accessing this property requires a running event loop when construction
is necessary. A closed borrowed session raises RuntimeError.

This property also accepts assignment. Install a caller-owned session without abandoning an open owned session.

Assigning the existing session preserves ownership. Replacing an open
internally created session raises RuntimeError; close it first. Borrowed
sessions are never closed when replaced or when this API is closed.

## PrydwenAPIClient

Scoped Prydwen HTTP operations and build-fetcher creation. `build_fetcher()` transfers lifecycle responsibility for the returned fetcher to its caller. Tier/code requests own and close their request transport.

```python
def __init__(*, proxy: str | None = None) -> None:
    ...
```

Store the default proxy; no network or filesystem side effects occur.

- `proxy: str | None`: Default request proxy.

### `build_fetcher`

```python
def build_fetcher(config: FetchConfig, *, nanoka: NanokaIndex | None = None) -> PrydwenFetcher:
    ...
```

Create a cache-first build fetcher using config's HTTP/browser transport.

The caller enters its async context and owns closure. Browser imports and
launches occur only for explicit browser transport when that context opens.

### `close`

```python
async def close() -> None:
    ...
```

Finish client ownership; each request already closes its scoped scraper.

### `get_html`

```python
async def get_html(url: str, *, timeout: float = 30.0, proxy: str | None = None) -> str:
    ...
```

Return a page body using a seconds timeout and an optional proxy override.

Raises ValueError for nonpositive timeout and propagates HTTP/dependency
errors. The request owns and closes its scraper, including on failure.

### `get_redeem_codes`

```python
async def get_redeem_codes(
    url: str = 'https://www.prydwen.gg/star-rail/codes',
    *,
    timeout: float = 30.0,
) -> list[RedeemCode]:
    ...
```

Return active codes and rewards, or an empty list if the page has none.

Fetches the page over HTTP; timeout is in seconds. Fetch errors propagate.

### `get_tier_list`

```python
async def get_tier_list(
    url: str = 'https://www.prydwen.gg/star-rail/tier-list',
    *,
    game_mode: GameMode = 'MOC',
    timeout: float = 30.0,
    proxy: str | None = None,
) -> TierListData:
    ...
```

Return parsed MOC, PF, or AS ranking data from one fetched page.

Mode aliases are case-insensitive. Raises ValueError before network access
for unsupported modes/timeouts and after parsing when rankings are absent.
A per-call proxy overrides the default proxy.
