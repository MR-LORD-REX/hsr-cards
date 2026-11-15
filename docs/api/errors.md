# Errors and empty results

Player card methods, tier-list facade rendering, and facade redeem-code fetches wrap ordinary failures in `HSR_Error` (`from hsr_cards.utils.errors import HSR_Error`). Standalone Nanoka card/provider errors generally propagate directly.

- Filtered single catalog lookups can return `None` when nothing matches.
- Catalog lists can be empty.
- Required detail/payload lookups raise provider errors when the entity is missing.
- Invalid modes, versions, floors, and look-ahead values raise `ValueError` where documented.
- AA current/next floor cards raise `NotImplementedError`.
- Batch rendering records ordinary errors per item and propagates cancellation.
- `verify_cookies()` returns `False` for absent/failed credentials.
- Next-card requests with a larger look-ahead or `"max"` can return `[]`; a single-result request raises when none resolves.

```python
from hsr_cards import HonkaiStarrail
from hsr_cards.utils.errors import HSR_Error

async def request():
    try:
        async with HonkaiStarrail("800556377") as client:
            image = await client.MOC()
            image.save("player-moc.png")
    except HSR_Error as error:
        print(str(error))
```

## Nanoka exceptions

Import these from `hsr_cards.providers.nanoka.exceptions` (or the compatible `hsr_cards.nanoka.exceptions`).

### `NanokaError`

Base exception for the Nanoka SDK.

### `NanokaHTTPError`

A failed HTTP request or invalid provider response.

Carry the requested URL, HTTP status (zero when unavailable), and diagnostic
message so callers can inspect failures without parsing the exception text.

- `url: str`: Requested resource URL.
- `status: int`: HTTP status, or zero when unavailable.
- `message: str`: Diagnostic message.

### `NanokaNotFoundError`

A requested provider resource has no published detail document.

Carry the resource kind and string-form identifier; optional lookup methods
may return None instead of raising this exception.

- `resource: str`: Missing resource kind.
- `identifier: str`: Requested resource identifier.

### `NanokaCacheError`

Raised when the local cache cannot be read, written, or validated.

### `NanokaAssetError`

Raised when an asset cannot be downloaded or resolved.
