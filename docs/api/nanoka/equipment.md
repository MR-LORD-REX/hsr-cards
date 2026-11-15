# Nanoka: Light Cones and relics

Query equipment catalogs, resolve a summary plus optional detail, or read a detail model directly. Light Cone details expose stats/refinements; relic details preserve piece data and set effects. `refresh=True` revalidates the active version/locale cache.

```python
from hsr_cards import NanokaClient

async def query():
    async with NanokaClient(include_assets=False) as client:
        cones = await client.list_lightcones(rarity=5)
        sets = await client.list_relics(search="Messenger")
        if cones:
            cone = await client.get_lightcone(cones[0].id)
            print(cone.display_name() if cone else None)
```

For images use [standalone card functions](../card-functions.md); field schemas are in [Nanoka models](../nanoka-models.md).

All async methods below belong to [NanokaClient](../nanoka-client.md).

## Methods

### `get_latest_lightcone`

```python
async def get_latest_lightcone(
    *,
    include_details: bool = False,
    refresh: bool = False,
    **filters: Any,
) -> LightCone | None:
    ...
```

Return the highest-ID matching light cone, or None for an empty catalog.

Details are omitted by default. Filters follow list_lightcones; refresh
revalidates cached data and detail/cache/transport errors propagate.

### `get_latest_relic`

```python
async def get_latest_relic(
    *,
    include_details: bool = False,
    refresh: bool = False,
    **filters: Any,
) -> RelicSet | None:
    ...
```

Return the highest-ID matching relic set, or None if no set matches.

Details are omitted by default; filters follow list_relics. Refresh revalidates
cached data and missing-detail/cache/transport failures propagate.

### `get_lightcone`

```python
async def get_lightcone(
    identifier: int | str | None = None,
    *,
    name: str | None = None,
    path: str | None = None,
    rarity: int | None = None,
    search: str | None = None,
    include_details: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> LightCone | None:
    ...
```

Find a light cone by numeric ID, localized name, or catalog filters.

A nonnumeric identifier becomes a search term. Return the first sorted match
with details by default, or None if absent. include_details=False skips detail
loading. Refresh revalidates catalogs; missing requested details raise
NanokaNotFoundError and cache/transport/model failures propagate.

### `get_lightcone_detail`

```python
async def get_lightcone_detail(identifier: int | str, *, refresh: bool = False) -> LightConeDetail:
    ...
```

Load a light-cone detail model by numeric ID for this version/locale.

refresh=True revalidates data. Missing details raise NanokaNotFoundError;
invalid IDs/models and cache/transport failures propagate.

### `get_relic`

```python
async def get_relic(
    identifier: int | str | None = None,
    *,
    name: str | None = None,
    search: str | None = None,
    include_details: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> RelicSet | None:
    ...
```

Find a relic set by numeric ID, localized name, or summary filters.

A nonnumeric identifier is a search term. Return the first match with details
by default, or None if absent. include_details=False skips detail loading;
refresh revalidates catalogs and detail/cache/transport errors propagate.

### `get_relic_detail`

```python
async def get_relic_detail(identifier: int | str, *, refresh: bool = False) -> RelicSetDetail:
    ...
```

Load a relic-set detail model by numeric ID for this version/locale.

refresh=True revalidates data. Missing details raise NanokaNotFoundError;
invalid IDs/models and cache/transport failures propagate.

### `list_lightcones`

```python
async def list_lightcones(
    *,
    path: str | None = None,
    rarity: int | None = None,
    search: str | None = None,
    sort_by: str = 'id',
    ascending: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> list[LightConeSummary]:
    ...
```

List light-cone summaries by path, numeric rarity, or localized search.

Extra filters compare attributes exactly. sort_by accepts id, rarity, name, or
atk (default id), with ascending=True. Return [] for no matches. Refresh
revalidates version/locale data; validation and cache/transport failures propagate.

### `list_relics`

```python
async def list_relics(
    *,
    search: str | None = None,
    sort_by: str = 'id',
    ascending: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> list[RelicSetSummary]:
    ...
```

List relic-set summaries by localized search and exact attribute filters.

sort_by=name orders by localized name; other values use ID, ascending by
default. Return [] for no matches. Refresh revalidates version/locale data;
validation and cache/transport failures propagate.
