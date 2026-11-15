# PrydwenClient

Read public Prydwen tier/code data or run the local build pipeline. Import with `from hsr_cards import PrydwenClient`. Collection methods are async; parsing, validation, approval, and build rendering are synchronous local operations.

```python
from hsr_cards import PrydwenClient

async def query():
    async with PrydwenClient() as client:
        tiers = await client.get_tier_list(game_mode="PF")
        print(tiers.mode, tiers.updated)
        codes = await client.get_redeem_codes()
        print([code.code for code in codes])
```

Build collection defaults to HTTP. `transport="browser"` requires the browser extra and an installed browser; build timeouts use milliseconds, tier/code timeouts use seconds. Drafts, reports, and contact sheets stay in `work_dir`; approved renders also publish under `build_dir/<slug>/`. The default work tree is the nearest existing ancestor `.hsr_prydwen`, otherwise `.hsr_prydwen` in the working directory. See the [build workflow](../guides/builds.md), [provider API](provider-apis.md), and [Prydwen models](prydwen-models.md).

## Constructor

```python
def __init__(
    *,
    work_dir: str | Path | None = None,
    build_dir: str | Path | None = None,
    nanoka_cache: str | Path | None = None,
    nanoka_version: str = '4.7.51',
    headed: bool = False,
    proxy: str | None = None,
    settle_ms: int = 5000,
    transport: str = 'http',
    refresh: bool = False,
    timeout_ms: int = 30000,
    retries: int = 2,
    chrome: str | Path = Path('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'),
    api: PrydwenAPIClient | None = None,
):
    ...
```

Configure independent build and query access with an optional caller-owned API.

work_dir contains drafts/reports; build_dir contains approved artifacts.
Reads existing Nanoka catalogs for nanoka_version, but creates no directories.
transport selects HTTP or explicit browser collection; timeouts are milliseconds
for builds. Injected api objects are never closed by this client.

## Configuration fields

These fields describe the configured instance. Use constructor options to set them.

- `api: PrydwenAPIClient`: Query/collection provider API; injected values remain caller-owned.
- `work_dir: Path`: Resolved local drafts and reports root.
- `build_dir: Path`: Approved build publication root.
- `raw_dir: Path`: Cached source HTML directory.
- `data_dir: Path`: Parsed build JSON and team-index directory.
- `cards_dir: Path`: Working render output directory.
- `urls_path: Path`: Saved character-roster manifest.
- `nanoka: NanokaIndex`: Matching local Nanoka catalog/asset index.
- `fetch_config: FetchConfig`: HTTP/browser collection settings.

## Queries

### `get_tier_list`

```python
async def get_tier_list(
    *,
    game_mode: GameMode = 'MOC',
    timeout: float = 30.0,
    proxy: str | None = None,
) -> TierListData:
    ...
```

Fetch MOC/PF/AS ranking data with case-insensitive mode aliases.

A per-call proxy overrides the API default. Invalid modes, nonpositive
timeouts, missing rankings, and HTTP errors raise before returning data.

### `get_redeem_codes`

```python
async def get_redeem_codes(*, timeout: float = 30.0) -> list[RedeemCode]:
    ...
```

Fetch active codes and reward models; timeout is measured in seconds.

Performs HTTP in a worker; dependency and HTTP failures propagate.

## Collection

### `urls`

```python
async def urls() -> Path:
    ...
```

Fetch the character roster and write rawUrls.json under work_dir.

Uses the configured cache/transport and closes the operation-owned fetcher.
Network, parsing, and filesystem failures propagate.

### `pull`

```python
async def pull(character: str | Iterable[str] | None = None, *, concurrency: int = 2) -> dict:
    ...
```

Cache selected character HTML with bounded concurrent fetches.

character accepts one name/slug, an iterable, or None for the saved roster.
Returns paths plus cached/downloaded counts and per-character failures.
Unknown selections or an empty roster raise ValueError; missing manifests raise.

## Local parsing and review

### `parse`

```python
def parse(character: str | Iterable[str] | None = None) -> dict:
    ...
```

Parse selected cached HTML into draft build JSON without network access.

character accepts one name/slug, an iterable, or None for all raw snapshots.
Returns written paths and per-file failures. Missing snapshots raise
FileNotFoundError and unavailable Nanoka catalogs raise ValueError.

### `validate`

```python
def validate(files: str | Path | Iterable[str | Path]) -> list[dict]:
    ...
```

Read one or several build JSON files and return review status and validation problems.

Performs local catalog/file checks without changing approval state. Missing
files and malformed build JSON raise instead of becoming per-file failures.

### `approve`

```python
def approve(
    character: str | None = None,
    *,
    file: str | Path | None = None,
    reviewer: str = 'manual',
    note: str | None = None,
) -> BuildCardData:
    ...
```

Validate and explicitly approve one character or file, recording reviewer and note.

Updates the selected draft JSON and returns BuildCardData. Missing selection
or failed validation raises ValueError; missing files propagate filesystem errors.

### `approve_all`

```python
def approve_all(
    character: str | Iterable[str] | None = None,
    *,
    reviewer: str = 'manual',
    note: str | None = None,
) -> dict:
    ...
```

Approve selected valid drafts, retaining and reporting individual failed entries.

character is a name/slug, iterable, or None for every draft. Returns approved
models and per-file failures; missing requested files or an empty data tree raises.

### `teams`

```python
def teams(*, allow_draft: bool = False) -> TeamIndex:
    ...
```

Write and return the cross-character team index from local build JSON.

Drafts are excluded unless allow_draft=True. Writes data_dir/teams.json;
no requests or approvals occur.

## Rendering

### `card`

```python
def card(
    character: str | None = None,
    *,
    data: str | Path | None = None,
    out: str | Path | None = None,
    allow_draft: bool = False,
    exclude_extra: bool = True,
) -> Path:
    ...
```

Render one local build and publish approved artifacts, returning the PNG path.

Supply character or data. Drafts require allow_draft=True. exclude_extra=True
produces the clean card; False adds detailed conditions. out and working
reports must remain outside build_dir. Invalid approved builds raise ValueError.
Writes local images/reports and, for approved builds, published asset metadata.

### `cards`

```python
def cards(
    character: str | Iterable[str] | None = None,
    *,
    out: str | Path | None = None,
    allow_draft: bool = False,
    exclude_extra: bool = True,
) -> dict:
    ...
```

Render selected local builds and return cards, contact sheets, and per-file failures.

character is a name/slug, iterable, or None for all JSON builds. Draft handling
and exclude_extra match card(). Writes working outputs outside build_dir and
publishes approved images. Empty input or output inside build_dir raises.

## Lifecycle

### `close`

```python
async def close() -> None:
    ...
```

Close an internally constructed API client, leaving injected APIs open.
