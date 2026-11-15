# Player cards

HoYoLAB cards visualize a player's records, calendar, and daily notes. They require a supported UID and HoYoLAB credentials. Pass explicit `Cookies` to keep your application's credential handling predictable.

```python
import os
from hsr_cards import HonkaiStarrail
from hsr_cards.models.auth import Cookies

cookie = Cookies(
    ltoken_v2=os.environ["ltoken_v2"],
    ltuid_v2=os.environ["ltuid_v2"],
)
async with HonkaiStarrail("800556377", cookie=cookie) as client:
    image = await client.PF(schedule_type="1")
    image.save("player-pure-fiction.png")
```

Applications may load an environment file before constructing credentials; HSR Cards does not load one on import. Requests without explicit cookies use configured `ltoken_v2` and `ltuid_v2` environment values where supported. `notes()` requires explicit cookies. A calendar request without explicit cookies also uses the configured `default_uid`; with explicit cookies it uses the player's UID.

## Challenge records

- `MOC(schedule_type="1")`: Memory of Chaos.
- `PF(schedule_type="1")`: Pure Fiction.
- `shadow(schedule_type="1")`: Apocalyptic Shadow.
- `anomaly()`: Anomaly Arbitration player record.

For MOC, PF, and AS, `"1"` selects the current cycle and `"2"` the previous cycle. These methods return PIL images. They differ from the Nanoka [floor-information cards](endgame.md).

## Calendar and notes

```python
async with HonkaiStarrail("800556377", cookie=cookie) as client:
    (await client.banners()).save("player-banners.png")
    (await client.events()).save("player-events.png")
    (await client.endgame()).save("player-endgame-calendar.png")
    image, notes = await client.notes(raw=True)
    image.save("player-notes.png")
    print(notes.current_stamina, notes.max_stamina)
```

`banners()`, `events()`, and `endgame()` draw calendar sections. `notes(raw=True)` returns `(Image, NotesData)`; otherwise it returns the image alone. `verify_cookies()` returns a boolean and returns `False` when credentials are absent or verification fails.

## Currency Wars

```python
async with HonkaiStarrail("800556377", cookie=cookie) as client:
    run = await client.currency_war(index=0)
    run.save("currency-wars.png")
    if run.has_next:
        older = await client.currency_war(index=run.next())
        older.save("currency-wars-older.png")
```

Runs follow API order, newest first. `next()`/`prev()` return adjacent indices, rather than rendering another image. `currency_war(raw=True)` returns `(CurrencyWarResult, CurrencyWarData)`. Invalid indices and card/API failures are wrapped in `HSR_Error`.

## Regions and lifecycle

UID prefixes `1` and `8` map to Asia, `6` to America, and `7` to Europe. Prefix `5` is currently unsupported. Invalid/unsupported UIDs fail before a query. Use the async context or call `await client.close()` to release owned provider sessions.

For data without drawing, use [HoYoLABClient](../api/hoyolab-client.md). See [facade signatures](../api/main-client.md), [result properties](../api/results.md), and the [player showcase](../showcase.md#player-moc).
