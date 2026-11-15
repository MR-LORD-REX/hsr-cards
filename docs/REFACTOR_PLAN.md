# Client and renderer refactor

Implemented 15 November 2026. MOC, PF, and AS floor cards retain the reference
behavior from the preparation baseline. AA floor cards remain deferred.

[Original client-boundary diagram](https://www.figma.com/board/NnDvWQKjcd6aBFpEqXeH5l)

## Responsibilities

`clients/main.py` contains the `HonkaiStarrail` facade. Its player and Nanoka card
methods are split into explicit-signature method modules. Provider clients are
independent: HoYoLAB queries validate player responses, Nanoka queries resolve
catalog/domain objects, and Prydwen queries expose tiers, codes, and the existing
build pipeline. Provider API clients handle raw data access and transport.

`services/` owns character loading, comparison preparation, rendered caches, and
endgame orchestration. Nanoka info, skills, and floor renderers draw resolved
models synchronously. HTTP calls, season selection, and client lifecycle stay
outside the floor drawing code. Pure locale, version, filename, parameter, and
image helpers are shared only where their behavior matches.

## Implemented layout

```text
src/hsr_cards/
  __init__.py                       # Lazy stable public exports
  client.py                         # Legacy facade module alias
  clients/
    main.py                         # Facade configuration, ownership, delegates
    player_cards.py                  # Explicit player-card method signatures
    nanoka_cards.py                  # Explicit non-player card signatures
    hoyolab.py                      # Validated player queries
    nanoka.py                       # Catalog/domain client
    prydwen.py                      # Tier/code/build client
  providers/
    hoyolab/{api,endpoints}.py
    hoyolab/models/
    nanoka/api.py                   # Raw catalog/detail/document/asset access
    nanoka/{catalogs,characters,equipment,items,monsters,schedules,assets}.py
    nanoka/models/                  # Character, monster, equipment, endgame, etc.
    nanoka/cache/                   # Controller, manifests, JSON, asset IO
    prydwen/{api,http,fetch,browser_fetch,models,assets,paths}.py
    prydwen/parsing/                # Build sections, tiers/DOM, codes, roster
  services/
    characters.py                   # Public info/skills/batch orchestration
    character_data.py               # Shared character loading and ownership
    character_info.py               # Info/comparison model preparation
    skills.py                       # Skills/comparison model preparation
    character_assets.py             # Targeted artwork preparation
    rendered_cache.py               # Stable rendered-card filenames and IO
    endgame/                        # API, data, results, HP, modes, assets, schedules
  renderer/
    common/{images,text,stars,team}.py
    nanoka/info/                    # Identity, material, stat, text, drawing models
    nanoka/skills/                  # Preparation, tables, mixed text, cards, layout
    nanoka/endgame/                 # Floor composition, nodes, effects, drawing
    hoyolab/                        # Existing player-card family
    prydwen/builds/                 # Build primitives, notes, card composition
  core/{types,locale,versions,paths,text}.py
  nanoka/                           # Legacy provider/client compatibility imports
  prydwen/                          # Legacy imports, CLI, registry, publication
  api/                              # Legacy HoYoLAB API compatibility imports
```

The legacy character renderer, data, and endgame modules forward to the extracted
implementations. Files were split by responsibility; established drawing and
cache behavior remain the compatibility baseline.

## Public contracts and ownership

Existing package-root exports, legacy module paths, callable parameters, result
objects, and `hsr-prydwen` CLI entry points remain supported. Newly explicit
client/API paths can be imported directly. Shared implementation objects are
re-exported rather than copied. Legacy modules used by existing monkeypatches
retain module identity where necessary.

Importing public APIs performs no cache-path discovery, directory creation,
credential loading, or session opening. `HonkaiStarrail()` supports non-player
operations without a UID. Player operations require a UID. HoYoLAB credentials
are explicit `Cookies(ltoken_v2=..., ltuid_v2=...)`; applications choose whether
to load environment files themselves.

The facade lazily creates its provider clients. Injected clients remain owned by
the caller. Closing the facade attempts to close every owned provider even when
another close fails. Provider clients likewise distinguish owned API/session
resources from injected ones.

Endgame public functions accept an optional initialized `client=` and reuse one
provider for every requested floor and season. Only internally created clients
are initialized and closed by the operation, including on failure. An injected
client's language controls render-cache localization. The facade forwards an
existing Nanoka client when available.

Both current/next card functions and facade methods use
`GameMode = Literal["MOC", "PF", "AS", "AA"]`. Runtime mode normalization still
accepts surrounding whitespace and lowercase names. MOC defaults to floors 11
and 12; PF and AS default to 3 and 4. `look_ahead=1` returns one upcoming season;
larger values and `"max"` return an ordered list. Test/deployment dates never
stand in for live dates, and undated upcoming seasons remain `UNSCHEDULED`.

Downloaded and rendered cache roots, filenames, locale suffixes, and comparison
keys retain their existing formats. Batch rendering records ordinary per-item
failures and propagates cancellation. Comparison/data-loading failures close
clients already created for that operation.

## Documentation and verification

Public/API functions, methods, properties, and model classes in the extracted
packages have docstrings. Service entry points document accepted version/mode
selections, return shapes, cache effects, and resource ownership. The README
includes independent client usage and explicit credential setup.

Offline tests cover compatibility imports, fresh-process import side effects,
client/API ownership, failure cleanup, cancellation, version switching, cache
invalidation, provider parsing, and reference drawing. MOC has a checked-in
reference fixture; PF/AS retain their independent Nanoka fixture. These checks
do not require a downloaded private cache or live provider access.

The established character anchors remain 1080x1440 for character 1507 at
4.7.51, and 1920x3188 with eight tables for character 1511 compared between
4.6.51 and 4.6.54. Source-preserving renderer extraction was checked against
pre-refactor pixel hashes and rich-message payloads.

Run the project interpreter with `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
& '.\.venv\Scripts\python.exe' -m pytest tests -q -p no:cacheprovider
& '.\.venv\Scripts\python.exe' -m compileall -q src tests
```

## Deferred AA work

Do not enable AA floor cards in this refactor. Existing PeakSchedule data has no
reliable live window, so current/next selection remains ambiguous. Both floor
card functions retain `NotImplementedError` for AA. Apply the user's proposed
date-resolution fix with current/next schedule regressions in a later version.
Existing HoYoLAB player AA cards remain available.
