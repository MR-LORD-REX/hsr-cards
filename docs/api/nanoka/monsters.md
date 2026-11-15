# Nanoka: Monsters

Query enemy summaries and resolve variants/base stats. `get_monster()` can include the original detail document; `get_monster_stats()` returns normalized stats when present. Missing single matches return `None`, while required detail lookups raise provider errors.

```python
from hsr_cards import NanokaClient

async def query():
    async with NanokaClient(include_assets=False) as client:
        monsters = await client.list_monsters(weakness="Fire")
        if monsters:
            monster = await client.get_monster(monsters[0].id)
            print(monster.display_name() if monster else None)
```

See [Nanoka models](../nanoka-models.md) for `MonsterDetail`, `MonsterVariant`, and `MonsterStats`.

All async methods below belong to [NanokaClient](../nanoka-client.md).

## Methods

### `get_latest_monster`

```python
async def get_latest_monster(
    *,
    include_details: bool = False,
    refresh: bool = False,
    **filters: Any,
) -> Monster | None:
    ...
```

Return the highest-ID matching monster, or None for an empty catalog.

Details are omitted by default. Filters follow list_monsters; refresh
revalidates cached data and detail/cache/transport errors propagate.

### `get_monster`

```python
async def get_monster(
    identifier: int | str | None = None,
    *,
    name: str | None = None,
    rank: str | None = None,
    weakness: str | None = None,
    search: str | None = None,
    include_details: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> Monster | None:
    ...
```

Find a monster by numeric ID, localized name, or catalog filters.

A nonnumeric identifier becomes search text. Return the first match with
details by default, or None when absent. include_details=False skips details;
refresh revalidates catalogs and detail/cache/transport failures propagate.

### `get_monster_detail`

```python
async def get_monster_detail(identifier: int | str, *, refresh: bool = False) -> MonsterDetail:
    ...
```

Load monster detail and variant models by numeric base ID.

refresh=True revalidates version/locale data. Missing details raise
NanokaNotFoundError; invalid IDs/models and cache/transport failures propagate.

### `get_monster_stats`

```python
async def get_monster_stats(identifier: int | str, *, refresh: bool = False) -> MonsterStats | None:
    ...
```

Return base scaling stats from monstervalue.json by numeric ID, or None if absent.

refresh=True revalidates data. This does not apply stage HP/difficulty modifiers;
validation and cache/transport errors propagate.

### `list_monsters`

```python
async def list_monsters(
    *,
    rank: str | None = None,
    weakness: str | None = None,
    search: str | None = None,
    sort_by: str = 'id',
    ascending: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> list[MonsterSummary]:
    ...
```

List monster summaries filtered by rank, weakness, localized search, and attributes.

Rank/weakness/search are case-insensitive. sort_by=name uses localized names;
other values use ID, ascending by default. Return [] for no matches. Refresh
revalidates version/locale data; validation and cache/transport errors propagate.
