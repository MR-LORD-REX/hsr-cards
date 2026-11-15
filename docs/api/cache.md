# NanokaCache

Low-level version/locale cache used by `NanokaAPIClient`. Import with `from hsr_cards.providers.nanoka.cache import NanokaCache`. Most applications can use `NanokaClient.cache` instead of constructing one.

Catalogs and artwork live under `<cache_dir>/<version>/<locale>/{data,assets}`. Global version metadata uses `<cache_dir>/manifest.json`. Path properties perform no writes. `ensure()`, `update()`, JSON access, and asset downloads may perform IO; explicit clear methods remove only their documented scope. See the [cache guide](../guides/caching.md) and [manifest fields](nanoka-models.md).

```python
from hsr_cards import NanokaClient

async def inspect_cache():
    async with NanokaClient(include_assets=False) as client:
        await client.initialize()
        print(client.cache.data_dir, client.cache.assets_dir)
        print(client.cache.read_manifest())
```

## Constructor

```python
def __init__(
    *,
    cache_dir: str | Path | None = None,
    version: str | None = None,
    locale: Locale | str = Locale.EN,
    base_url: str = 'https://static.nanoka.cc/hsr',
    asset_base_url: str = 'https://static.nanoka.cc/assets/hsr',
    manifest_url: str = 'https://static.nanoka.cc/manifest.json',
    http: AsyncHTTP | None = None,
    include_assets: bool = True,
    concurrency: int = 16,
    auto_update: bool = False,
):
    ...
```

Configure version/locale storage and an optional caller-owned HTTP transport.

cache_dir defaults to .nanoka_cache under the caller working directory.
version pins a build; None permits later discovery of the newest published
build. locale accepts Locale aliases. CDN/manifest URLs control downloads,
include_assets controls bulk asset loading, auto_update revalidates on access,
and concurrency is clamped to at least one. Construction creates no cache
files or HTTP session. Injected http remains open when this cache closes;
invalid locale aliases raise ValueError.

## Configuration fields

These fields describe the configured instance. Use constructor options to set them.

- `cache_dir: Path`: Cache root.
- `version: str | None`: Pinned/resolved build.
- `locale: Locale`: Active localized tree.
- `base_url: str`: Catalog CDN base.
- `asset_base_url: str`: Artwork CDN base.
- `manifest_url: str`: Root version-manifest URL.
- `include_assets: bool`: Bulk artwork initialization setting.
- `concurrency: int`: Bounded download concurrency.
- `auto_update: bool`: Revalidation preference.

## Methods and properties

### `asset`

```python
async def asset(relative: str, *, download: bool = True) -> Path | None:
    ...
```

Return a cached asset path, downloading the relative CDN file when missing.

download=False skips single-file downloading, but initialization still ensures
the cache. Explicit downloads work when bulk include_assets=False. Missing
assets return None; successful downloads update the locale manifest and
initialization/cache errors propagate.

### `asset_file`

```python
def asset_file(relative_path: str) -> Path:
    ...
```

Return an asset-relative path under the active version/locale asset directory.

### `assets_dir`

```python
assets_dir: Path
```

Return the active locale asset directory without creating it.

### `clear`

```python
async def clear() -> None:
    ...
```

Remove only this version/locale directory, never the whole cache root.

### `clear_version`

```python
async def clear_version(version: str | None = None) -> None:
    ...
```

Remove one complete version tree, or every version when omitted.

### `close`

```python
async def close() -> None:
    ...
```

Close the cache-owned HTTP transport; an injected transport remains open.

### `data_dir`

```python
data_dir: Path
```

Return the active locale JSON directory without creating it.

### `ensure`

```python
async def ensure(*, force: bool = False, update: bool = False) -> CacheManifest:
    ...
```

Ensure a complete version/locale cache and return its CacheManifest.

force/update/auto_update revalidate data; otherwise complete cached files are
reused. Unpinned versions resolve from the global manifest. include_assets
controls bulk downloads. Concurrent initialization is serialized; network,
validation, and NanokaCacheError failures propagate.

### `exists`

```python
def exists() -> bool:
    ...
```

Return whether an active version/locale manifest file exists on disk.

### `load_json`

```python
async def load_json(relative_path: str, *, required: bool = True) -> Any | None:
    ...
```

Read a cache-relative JSON document after asynchronously ensuring the cache.

Return None for an absent optional file. required=True or malformed JSON
raises NanokaCacheError; initialization may download and write cache files.

### `locale_dir`

```python
locale_dir: Path
```

Return the active build/locale directory without creating it.

### `manifest_path`

```python
manifest_path: Path
```

Return the active locale cache manifest path without creating it.

### `path_for`

```python
def path_for(relative_path: str) -> Path:
    ...
```

Return a data-relative path under the active version/locale JSON directory.

### `read_manifest`

```python
def read_manifest() -> CacheManifest | None:
    ...
```

Read the active locale manifest, reusing the matching in-memory model.

Return None for absent/version-mismatched data. Invalid JSON/models raise
NanokaCacheError; matching metadata updates validators and the live version.

### `resolve_version`

```python
async def resolve_version() -> str:
    ...
```

Resolve the newest published build unless the caller pinned one.

If the CDN is unreachable but a complete cache exists, keep serving it
instead of turning every call into a network failure.

### `update`

```python
async def update(*, force: bool = False) -> CacheManifest:
    ...
```

Revalidate catalogs and optional assets and return the active CacheManifest.

force=True replaces cached data; network/cache failures propagate. Version
resolution and download ownership follow ensure().

### `validator`

```python
async def validator(url: str) -> dict[str, str] | None:
    ...
```

Return conditional HTTP headers recorded for a CDN URL, or None if unknown.

The URL must resolve within this version/locale cache; no request is performed.

### `version_dir`

```python
version_dir: Path
```

Return the active build directory under the configured cache root.

### `versions`

```python
async def versions(*, refresh: bool = False) -> NanokaVersions:
    ...
```

Return the published HSR builds advertised by the root manifest.

### `write_global_manifest`

```python
async def write_global_manifest(payload: Any) -> None:
    ...
```

Cache the root manifest for offline `get_versions` calls.
