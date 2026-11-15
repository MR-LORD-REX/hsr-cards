# NanokaClient

Read versioned, localized Nanoka data without a player UID. Import with `from hsr_cards import NanokaClient`. Query methods return typed summaries, domain wrappers, details, or local asset paths.

```python
from hsr_cards import NanokaClient

async def lookup():
    async with NanokaClient(version="4.7.51", language="en", include_assets=False) as client:
        characters = await client.list_characters(rarity=5, include_beta=False)
        for character in characters:
            print(character.id, character.display_name())
```

Construction is offline. A first async query initializes missing catalogs; `initialize()` makes this explicit. Injecting an `api_client` keeps that API's own configuration and ownership. Domain wrappers expose `.summary`, `.detail`, `.locale`, and summary-first attribute lookup; see [results](results.md).

## Query reference

- [Characters](nanoka/characters.md): catalogs, resolved details, published builds.
- [Light Cones and relics](nanoka/equipment.md): equipment catalogs and refinements/effects.
- [Monsters](nanoka/monsters.md): enemies, variants, scaled stats.
- [Schedules and bosses](nanoka/schedules.md): MOC/PF/AS/AA data and date windows.
- [Items, achievements, and Currency Wars](nanoka/items-currency.md).
- [Assets and materials](nanoka/assets.md): cached local artwork paths.

See [model fields](nanoka-models.md), [provider API](provider-apis.md), [cache API](cache.md), and [caching guide](../guides/caching.md).

## Constructor

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
    api_client: NanokaAPIClient | None = None,
):
    ...
```

Configure the domain client and optional caller-owned provider API.

Without api_client, forward version/Locale aliases, caller-relative cache
root, CDN bases, proxy, timeout/retries, asset refresh settings, and
concurrency to a new NanokaAPIClient. version=None resolves the newest
published build on first async query. An injected API keeps its own
configuration and is never closed here. Invalid language aliases raise
ValueError. Construction performs no downloads or cache writes.

## Configuration fields

- `api_client: NanokaAPIClient`: Underlying provider API, owned internally unless injected.
- `language: Locale`: Normalized active locale: EN, ZH, JA, or KO.
- `version: str | None`: Selected build, synchronized after initialization or an explicit version update.
- `cache_dir: Path`: Downloaded-data cache root.
- `base_url: str`: Nanoka catalog CDN base.
- `asset_base_url: str`: Nanoka artwork CDN base.
- `include_assets: bool`: Whether cache initialization downloads bulk artwork.
- `auto_update: bool`: Whether cache ensure operations revalidate automatically.

## Cache and lifecycle

### `cache`

```python
cache: NanokaCache
```

Return the provider cache without initializing or downloading data.

### `cache_path`

```python
cache_path: Path
```

Return the active version/locale directory under the configured cache root.

### `initialize`

```python
async def initialize(*, force: bool = False) -> NanokaClient:
    ...
```

Download missing catalogs/assets, optionally replacing the cached build.

Return this client after synchronizing the resolved version. Network/cache
errors propagate; an unpinned first call may select a newer published build.

### `get_versions`

```python
async def get_versions(*, refresh: bool = False) -> NanokaVersions:
    ...
```

Return published builds and live/beta versions, optionally refreshing metadata.

### `update_assets`

```python
async def update_assets(*, version: str | None = None, force: bool = False) -> NanokaClient:
    ...
```

Refresh data/assets, switching to a published build when supplied.

Unknown versions raise ValueError before changing the active build. Cache
and transport failures propagate; return this client for chained queries.

### `clear_cache`

```python
async def clear_cache(*, version: str | None = None) -> None:
    ...
```

Remove one cached build, or all builds and global metadata when omitted.

### `close`

```python
async def close() -> None:
    ...
```

Close an internally created API client; injected clients remain open.
