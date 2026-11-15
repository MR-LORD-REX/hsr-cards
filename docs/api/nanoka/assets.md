# Nanoka: Assets and materials

Asset methods return local `Path` objects after cache initialization or targeted downloads. Missing/unavailable artwork can return `None`; paths belong to the active build and locale. `include_assets=False` skips bulk artwork during initialization while explicit downloads remain available.

```python
from hsr_cards import NanokaClient

async def query():
    async with NanokaClient(version="4.7.51", include_assets=False) as client:
        art = await client.character_assets(1507)
        materials = await client.character_materials(1507)
        print(art.keys(), materials.keys())
```

See [cache API](../cache.md) and [caching guide](../../guides/caching.md).

All async methods below belong to [NanokaClient](../nanoka-client.md).

## Methods

### `asset_path`

```python
async def asset_path(value: str, *, refresh: bool = False) -> Path | None:
    ...
```

Resolve an icon path, `kind:id` key, or bare ID to a cached local file.

Return None for unknown aliases or missing assets. This initializes the
JSON cache and reads its catalogs but does not request the individual
asset. Refresh revalidates data; cache/transport failures propagate.

### `character_assets`

```python
async def character_assets(
    identifier: int | str,
    *,
    include_skills: bool = True,
    refresh: bool = False,
) -> dict[str, Path]:
    ...
```

Return available character art, element/path, eidolon/trace, and relic icons.

identifier is numeric; include_skills=True also adds standard skill icons.
Return an alias-to-local-Path mapping; unavailable assets are omitted.
Refresh revalidates detail data and missing assets are downloaded. Missing
detail raises NanokaNotFoundError; cache/transport/model errors propagate.

### `character_materials`

```python
async def character_materials(identifier: int | str, *, refresh: bool = False) -> dict[str, Any]:
    ...
```

Group character material requirements and recommended build data by numeric ID.

Return ascension/trace costs, skills, lightcones, relics, and teams from
the parsed detail model. Refresh revalidates version/locale data. Missing
details raise NanokaNotFoundError; model/cache/transport errors propagate.

### `download_asset`

```python
async def download_asset(value: str, *, refresh: bool = False) -> Path | None:
    ...
```

Resolve an icon path, `kind:id` alias, or bare ID and fetch a missing asset.

Return the local Path, or None when resolution/download is unavailable.
Refresh revalidates the version/locale cache; catalog/cache/transport
failures propagate and successful downloads update the asset manifest.

### `fetch_asset`

```python
async def fetch_asset(relative: str, *, refresh: bool = False) -> Path | None:
    ...
```

Download one asset by its CDN-relative path.

`relative` is the path below `https://static.nanoka.cc/assets/hsr/`
(for example `skillicons/SkillIcon_1415_Ultra.webp`). This avoids a
full asset-bundle initialization when a card only needs a few icons.
Missing assets return None. Refresh revalidates the configured cache;
initialization/cache/transport failures propagate. Return the local Path
from the provider API and retain its resolved version.
