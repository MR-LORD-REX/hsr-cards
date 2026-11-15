# HoYoLABClient

Query player records without drawing a card. Import with `from hsr_cards.clients.hoyolab import HoYoLABClient`. Challenge records remain provider dictionaries; notes, calendar, and Currency Wars responses are validated models.

```python
import os
from hsr_cards.clients.hoyolab import HoYoLABClient
from hsr_cards.models.auth import Cookies

async def query():
    cookie = Cookies(ltoken_v2=os.environ["ltoken_v2"], ltuid_v2=os.environ["ltuid_v2"])
    async with HoYoLABClient("800556377", cookie=cookie) as client:
        notes = await client.get_notes()
        print(notes.current_stamina, notes.max_stamina)
```

UID prefixes 1/8 select Asia, 6 America, and 7 Europe; 5 is unsupported. Explicit cookies are required for notes. Other supported requests may use `ltoken_v2`/`ltuid_v2` from the application environment; calendar requests without explicit cookies additionally use `default_uid`. No environment file is loaded on import. An injected API remains caller-owned. See [player usage](../guides/player-cards.md), [provider API](provider-apis.md), and [HoYoLAB models](hoyolab-models.md).

## Constructor

```python
def __init__(
    uid: int | str,
    cookie: Cookies | None = None,
    proxy: str | None = None,
    *,
    api: BaseAPI | None = None,
):
    ...
```

Store player configuration; an injected API remains owned by its caller.

## Configuration fields

These fields describe the configured instance. Use constructor options to set them.

- `uid: str`: Configured player UID.
- `cookie: Cookies | None`: Explicit credentials, when supplied.
- `proxy: str | None`: Provider request proxy.

## Properties

### `api`

```python
api: BaseAPI
```

Return the configured API, constructing an IO-free default when needed.

### `server`

```python
server: Server
```

Infer the supported HoYoLAB server from the UID, raising ValueError if invalid.

## Challenge records

### `get_moc`

```python
async def get_moc(schedule_type: Schedule = '1') -> dict[str, Any]:
    ...
```

Fetch all player floors for the current (1) or previous (2) MOC cycle.

### `get_pf`

```python
async def get_pf(schedule_type: Schedule = '1') -> dict[str, Any]:
    ...
```

Fetch all player floors for the current (1) or previous (2) PF cycle.

### `get_shadow`

```python
async def get_shadow(schedule_type: Schedule = '1') -> dict[str, Any]:
    ...
```

Fetch all player floors for the current (1) or previous (2) AS cycle.

### `get_anomaly`

```python
async def get_anomaly() -> dict[str, Any]:
    ...
```

Fetch the player's AA response without creating a card.

## Calendar and player state

### `get_calendar`

```python
async def get_calendar() -> CalendarData:
    ...
```

Return a validated calendar; API failures raise HSR_Error and malformed JSON raises ValidationError.

### `get_notes`

```python
async def get_notes() -> NotesData:
    ...
```

Return validated authenticated daily notes; explicit cookies are required.

Missing cookies or a nonzero API return code raises HSR_Error. Invalid
response schemas raise pydantic.ValidationError.

### `get_currency_war`

```python
async def get_currency_war() -> CurrencyWarData:
    ...
```

Return validated recent Currency Wars runs, raising HSR_Error for API errors.

### `verify_cookies`

```python
async def verify_cookies() -> bool:
    ...
```

Check explicit cookies through daily notes; absent cookies or request errors return False.

## Lifecycle

### `close`

```python
async def close() -> None:
    ...
```

Close the owned API only, without constructing a previously unused API.
