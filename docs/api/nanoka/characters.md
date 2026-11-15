# Nanoka: Characters

Character methods share numeric-ID and published-name selection. Lists return `CharacterSummary` values; resolved lookups return `Character` wrappers or `None`. `include_details=True` loads the detail document. Filters, sorting, and refresh options are explicit in each signature. Published build cards are distinct from character info cards.

```python
from hsr_cards import NanokaClient

async def query():
    async with NanokaClient(include_assets=False) as client:
        catalog = await client.list_characters(element="Lightning", rarity=5)
        character = await client.get_character(name="Acheron")
        if character is not None:
            print(character.display_name(), character.summary, character.detail)
```

See [character guide](../../guides/characters.md) and [build guide](../../guides/builds.md).

All async methods below belong to [NanokaClient](../nanoka-client.md).

## Methods

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

Return one clean card, or the detailed summary and condition pages.

`url=True` returns GitHub raw links. `detailed=True` always returns
a list, with the summary first. Missing variants return `None`.
Local id/name lookups work without downloading the Nanoka catalog.

### `get_character`

```python
async def get_character(
    identifier: int | str | None = None,
    *,
    name: str | None = None,
    element: str | None = None,
    path: str | None = None,
    rarity: int | None = None,
    released: bool | None = None,
    include_beta: bool = True,
    search: str | None = None,
    include_details: bool = True,
    sort_by: str = 'release',
    ascending: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> Character | None:
    ...
```

Find by numeric ID, localized name, or any list_characters catalog filter.

A nonnumeric identifier becomes search text. Return the first sorted
matching Character wrapper, or None if absent. Details are included by
default; include_details=False skips their loading. Refresh revalidates
version/locale data. Missing requested details raise NanokaNotFoundError;
invalid ID/model and cache/transport failures propagate.

### `get_character_detail`

```python
async def get_character_detail(identifier: int | str, *, refresh: bool = False) -> CharacterDetail:
    ...
```

Load a character detail model by numeric ID for this client locale/version.

refresh=True revalidates cached data. Missing details raise NanokaNotFoundError;
invalid IDs/models and cache/transport failures propagate.

### `get_latest_character`

```python
async def get_latest_character(
    *,
    include_beta: bool = True,
    include_details: bool = False,
    element: str | None = None,
    path: str | None = None,
    rarity: int | None = None,
    refresh: bool = False,
) -> Character | None:
    ...
```

Newest character.

With `include_beta=True`, unreleased entries win and the highest ID
among them is returned (IDs increase with new reveals). Otherwise the
newest released character by release timestamp.
Path/element/rarity filters follow list_characters. Details are omitted
by default; return None for an empty catalog. Refresh revalidates
version/locale data and detail/cache/transport failures propagate.

### `list_characters`

```python
async def list_characters(
    *,
    element: str | None = None,
    path: str | None = None,
    rarity: int | None = None,
    released: bool | None = None,
    include_beta: bool = True,
    search: str | None = None,
    sort_by: str = 'release',
    ascending: bool = True,
    refresh: bool = False,
    **filters: Any,
) -> list[CharacterSummary]:
    ...
```

List character summaries matching catalog filters in the chosen order.

Beta entries are included by default; released compares release timestamps.
Path/element/search are case-insensitive, rarity is numeric, and extra filters
compare summary attributes exactly. sort_by accepts release, id, rarity, or name
(default release), with ascending=True. Refresh revalidates disk/network data.
Return [] when no entries match; validation and cache/transport errors propagate.
