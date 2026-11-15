# Nanoka: Items, achievements, and Currency Wars

Item and achievement methods read the localized catalogs. Currency Wars methods return typed roles, traits, augments, buffs, and items for game data, independently of the HoYoLAB player-run card.

```python
from hsr_cards import NanokaClient

async def query():
    async with NanokaClient(include_assets=False) as client:
        items = await client.list_items(search="Jade")
        roles = await client.list_currency_roles()
        print(len(items), len(roles))
```

See [Nanoka models](../nanoka-models.md) for field schemas and [player guide](../../guides/player-cards.md) for personal Currency Wars runs.

All async methods below belong to [NanokaClient](../nanoka-client.md).

## Methods

### `get_achievement`

```python
async def get_achievement(
    identifier: int | str,
    *,
    refresh: bool = False,
) -> AchievementSeries | None:
    ...
```

Return an achievement series by numeric ID, or None if absent.

The identifier names a series, not an individual achievement. Refresh revalidates
locale/version data and model/cache/transport errors propagate.

### `get_currency_role`

```python
async def get_currency_role(identifier: int | str, *, refresh: bool = False) -> CurrencyRole | None:
    ...
```

Return a Currency Wars role by numeric ID, or None if absent.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_currency_trait`

```python
async def get_currency_trait(
    identifier: int | str,
    *,
    refresh: bool = False,
) -> CurrencyTrait | None:
    ...
```

Return a Currency Wars trait by numeric ID, or None if absent.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_item`

```python
async def get_item(
    identifier: int | str | None = None,
    *,
    name: str | None = None,
    search: str | None = None,
    refresh: bool = False,
    **filters: Any,
) -> ItemSummary | None:
    ...
```

Find an item by numeric ID, name/search text, or catalog filters.

Nonnumeric identifiers become search terms. Return the first ID-ordered match
or None; filters follow list_items. Refresh revalidates version/locale data
and validation/cache/transport errors propagate.

### `get_latest_achievement`

```python
async def get_latest_achievement(
    *,
    refresh: bool = False,
    **filters: Any,
) -> AchievementSeries | None:
    ...
```

Return the highest-ID achievement series matching the supplied filters, or None.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_latest_currency_augment`

```python
async def get_latest_currency_augment(*, refresh: bool = False) -> CurrencyAugment | None:
    ...
```

Return the highest-ID Currency Wars augment, or None for an empty catalog.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_latest_currency_buff`

```python
async def get_latest_currency_buff(*, refresh: bool = False) -> CurrencyBuff | None:
    ...
```

Return the highest-ID Currency Wars buff, or None for an empty catalog.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_latest_currency_item`

```python
async def get_latest_currency_item(*, refresh: bool = False) -> CurrencyItem | None:
    ...
```

Return the highest-ID Currency Wars item, or None for an empty catalog.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_latest_currency_role`

```python
async def get_latest_currency_role(*, refresh: bool = False) -> CurrencyRole | None:
    ...
```

Return the highest-ID Currency Wars role, or None for an empty catalog.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_latest_currency_trait`

```python
async def get_latest_currency_trait(*, refresh: bool = False) -> CurrencyTrait | None:
    ...
```

Return the highest-ID Currency Wars trait, or None for an empty catalog.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `get_latest_item`

```python
async def get_latest_item(*, refresh: bool = False, **filters: Any) -> ItemSummary | None:
    ...
```

Return the highest-ID item matching list_items filters, or None.

Refresh revalidates version/locale data; model/cache/transport errors propagate.

### `list_achievements`

```python
async def list_achievements(
    *,
    search: str | None = None,
    refresh: bool = False,
    **filters: Any,
) -> list[AchievementSeries]:
    ...
```

List achievement series by series/achievement name search and exact attributes.

Return series ordered by descending priority then ID, or [] if unavailable.
Refresh revalidates locale/version data; model/cache/transport errors propagate.

### `list_currency_augments`

```python
async def list_currency_augments(
    *,
    search: str | None = None,
    refresh: bool = False,
) -> list[CurrencyAugment]:
    ...
```

List Currency Wars augments, optionally filtered by case-insensitive name search.

Return [] when the optional catalog is absent. Refresh revalidates the
version/locale cache; model/cache/transport errors propagate.

### `list_currency_buffs`

```python
async def list_currency_buffs(
    *,
    search: str | None = None,
    refresh: bool = False,
) -> list[CurrencyBuff]:
    ...
```

List Currency Wars buffs, optionally filtered by case-insensitive name search.

Return [] when the optional catalog is absent. Refresh revalidates the
version/locale cache; model/cache/transport errors propagate.

### `list_currency_items`

```python
async def list_currency_items(
    *,
    search: str | None = None,
    refresh: bool = False,
) -> list[CurrencyItem]:
    ...
```

List Currency Wars items, optionally filtered by case-insensitive name search.

Return [] when the optional catalog is absent. Refresh revalidates the
version/locale cache; model/cache/transport errors propagate.

### `list_currency_roles`

```python
async def list_currency_roles(
    *,
    search: str | None = None,
    refresh: bool = False,
) -> list[CurrencyRole]:
    ...
```

List Currency Wars roles, optionally filtered by case-insensitive name search.

Return [] when the optional catalog is absent. Refresh revalidates the
version/locale cache; model/cache/transport errors propagate.

### `list_currency_traits`

```python
async def list_currency_traits(
    *,
    search: str | None = None,
    refresh: bool = False,
) -> list[CurrencyTrait]:
    ...
```

List Currency Wars traits, optionally filtered by case-insensitive name search.

Return [] when the optional catalog is absent. Refresh revalidates the
version/locale cache; model/cache/transport errors propagate.

### `list_items`

```python
async def list_items(
    *,
    search: str | None = None,
    category: str | None = None,
    rarity: int | None = None,
    refresh: bool = False,
    **filters: Any,
) -> list[ItemSummary]:
    ...
```

List items by category, numeric rarity, name/description search, and attributes.

Prefer item_all.json and fall back to item.json when unavailable. Return
matching summaries in ID order, or [] if absent. Refresh revalidates the
version/locale cache; model/cache/transport errors propagate.
