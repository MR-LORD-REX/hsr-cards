# Endgame floor cards

Nanoka floor cards describe the enemies and mechanics in a published cycle. They are independent of a player's challenge record. Use `MOC`, `PF`, or `AS`; `AA` floor cards remain deferred.

## Current floors

```python
from hsr_cards import get_current_endgame_card

season = await get_current_endgame_card("PF", floors=[3, 4])
for card in season.cards:
    card.save(f"pf-{season.season_id}-floor-{card.floor}.png")
```

MOC defaults to floors 11 and 12. PF and AS default to floors 3 and 4. Supply an integer for one floor or a sequence for several. Selections are deduplicated and sorted. PF includes complete spawn waves and counts; AS includes boss mechanics and Starward mode. Floor continuations stay attached to their logical floor.

Both functions and their facade methods annotate the mode with `Literal["MOC", "PF", "AS", "AA"]` for editor suggestions. Lowercase codes and surrounding whitespace are normalized at runtime.

## Upcoming cycles

```python
from hsr_cards import get_next_endgame_card

next_season = await get_next_endgame_card("AS", floors=4)
next_season.cards[0].save("as-next-floor4.png")

all_upcoming = await get_next_endgame_card("MOC", look_ahead="max")
for season in all_upcoming:
    print(season.season_id, season.begins_at, season.ends_at)
```

`look_ahead=1` returns one `EndgameCardResult`. Larger positive values and `"max"` return a list ordered by live start time. Seasons without live windows follow dated seasons and show `UNSCHEDULED`; their card result's live dates are `None`. Stage documents that cannot be resolved are skipped. Missing current data or an empty single-result request raises `ValueError`; a multi-result request may return `[]`.

Deployment/test dates are not authoritative live dates. The card service requires a live window for current cards and includes status in rendered-cache keys so an upcoming badge can change when a season goes live.

## Reuse a Nanoka client

```python
from hsr_cards import NanokaClient, get_current_endgame_card

async with NanokaClient(version="4.7.51", language="en", include_assets=False) as client:
    await client.initialize()
    card = await get_current_endgame_card("PF", floors=4, client=client)
```

An injected initialized client remains caller-owned; its language controls localized rendered-cache filenames. Otherwise the service creates one client, reuses it for all requested floors and seasons, and closes it on success or failure.

## Result properties

A season result exposes `game_mode`, `season_id`, `season_name`, `version`, `cards`, `images`, `begins_at`, `ends_at`, `is_live`, and the compatibility aliases `start` and `end`. Each floor card exposes `image`, `floor`, `stage_id`, `name`, `cache_path`, and `save()`.

The broader Nanoka SDK also exposes schedule/domain objects whose effective dates may fall back to test windows. Use a floor card result's `begins_at`/`ends_at`, or the schedule's explicit `live_begins_at`/`live_ends_at`, when live timing matters.

## Anomaly Arbitration

Both floor-card entry points raise `NotImplementedError` for `AA` until reliable live-date selection is available. This does not disable the existing HoYoLAB `HonkaiStarrail.anomaly()` player-record card.

See [full signatures](../api/card-functions.md), [schedule queries](../api/nanoka/schedules.md), and [demo outputs](../showcase.md#endgame-current).
