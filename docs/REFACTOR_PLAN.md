# Client and renderer refactor preparation

Prepared 15 November 2026. This is the proposed migration plan; the package-wide
moves have not started. PF and AS floor-card support is the baseline to preserve.
AA floor cards stay deferred for a later version.

[Editable client-boundary diagram](https://www.figma.com/board/NnDvWQKjcd6aBFpEqXeH5l)

## Objectives and boundaries

Separate the main convenience client, provider clients, provider API access,
card orchestration, and drawing. Keep Nanoka and Prydwen usable without a player
UID, HoYoLAB cookies, or construction of a HoYoLAB session. Preserve existing
imports, method signatures, return objects, cache locations, and image behavior
throughout the migration.

A provider API client handles HTTP requests and response decoding. A provider
client resolves domain objects and exposes catalog/query operations. A card
service loads those objects, resolves assets, reads/writes rendered caches, and
calls a renderer. A renderer accepts resolved data and returns a PIL image;
it does not perform HTTP calls or select live seasons. The main facade only
delegates to these components and owns components it creates.

Do not force provider-specific authentication, browser scraping, catalog formats,
or cache invalidation into one generic base client. Share small utilities only
when the behavior is actually identical.

## Current seams to extract

- `client.py` (about 580 lines) combines HoYoLAB player methods, Nanoka render
  delegates, Prydwen operations, build assets, and session ownership.
- `nanoka/client.py` (about 1,660 lines) combines transport/cache setup, catalog
  filtering, version resolution, schedule selection, assets, and result wrappers.
- `nanoka/models.py` (about 1,640 lines) combines character, monster, endgame,
  item, currency, and cache models.
- `nanoka/cache.py` (about 910 lines) combines version manifests, JSON storage,
  downloading, assets, and invalidation.
- `renderer/nanoka/endgames.py` (about 1,050 lines) combines result types, data
  loading, HP calculations, schedules, caching, layout, and public orchestration.
  `endgame_modes.py` now isolates the PF wave and AS effect adapters.
- `renderer/nanoka/character_skills.py` (about 2,615 lines) and
  `character_variants.py` (about 1,010 lines) should split by data preparation,
  comparison, layout, and drawing responsibilities.
- `prydwen/builds/parse.py` (about 880 lines), `render.py` (about 700), and
  `prydwen/tier_list.py` (about 590) should split along fetch/parse/model/render
  boundaries. Keep CLI and publication workflows separate from the query client.
- Package-root imports currently pull in Prydwen modules eagerly, producing
  path-discovery output during imports. Capture this behavior in a regression
  before making provider exports lazy.
- Endgame public calls currently create a discovery client and another client
  for each season. Use one explicitly owned provider client per card operation.
  Replace renderer calls to `_prepare()` and `_detail()` with public provider APIs.

Line counts are approximate and describe this preparation baseline.

## Proposed layout

```text
src/hsr_cards/
  __init__.py                       # Stable lazy public exports
  client.py                         # Compatibility export of HonkaiStarrail
  clients/
    main.py                         # HonkaiStarrail facade
    hoyolab.py                      # Player query client
    nanoka.py                       # Catalog/domain client
    prydwen.py                      # Prydwen query/build facade
  providers/
    hoyolab/
      api.py                        # Existing BaseAPI operations
      endpoints.py
      models/
    nanoka/
      api.py                        # HTTP, catalogs, detail access
      catalogs.py                   # Catalog lookup and filtering
      schedules.py                  # Live/test windows and ordering
      assets.py
      versions.py
      cache/
        json_store.py
        manifests.py
        assets.py
      models/
        characters.py
        monsters.py
        endgame.py
        items.py
        currency.py
        cache.py
    prydwen/
      api.py                        # HTTP/browser transport adapters
      models.py
      parsing/
        builds.py
        tiers.py
        codes.py
  services/
    endgame/
      api.py                        # get_current/get_next orchestration
      results.py                    # EndgameCardResult/EndgameFloorCard
      data.py                       # Resolved floor/node data
      hp.py                         # Variants, phases, scaling, corrosion
      modes.py                      # PF/AS adapters
    characters.py
    builds.py
  renderer/                         # Existing family boundaries stay
    common/
      text.py                       # Wrapping and measured text blocks
      images.py                     # Image fitting/compositing
      elements.py
      stars.py
      team.py
    nanoka/
      endgame/
        layout.py
        nodes.py
        effects.py
      skills/
        layout.py
        tables.py
        sections.py
      endgames.py                    # Compatibility re-exports
    hoyolab/
    prydwen/
  core/
    http.py                         # Only transport behavior shared by providers
    paths.py                        # Explicit roots and safe filenames
    locale.py
    text.py                         # Shared markup/parameter rules where identical
  nanoka/                           # Compatibility exports during migration
  prydwen/                          # Compatibility exports and existing CLI
  api/                              # Compatibility exports of HoYoLAB API
```

The tree is a responsibility map. Introduce each package only when moving real
code into it. Preserve provider-specific options and avoid empty scaffolding.
Keep existing `utils/` entry points as forwarding imports when extracting shared
helpers. Existing `renderer/hoyolab/endgame.py` remains the HoYoLAB schedule card;
Nanoka floor cards retain their own service and renderer.

## Migration sequence

1. **Freeze contracts and references.** Record import paths and signatures for
   root exports, the three existing clients, card results, and the CLI. Preserve
   the independent PF/AS snapshots in `tests/fixtures/endgame_reference.json`.
   Add independent MOC fixtures so its regressions no longer require a private
   local Nanoka cache. Retain the established character render anchors.
2. **Extract endgame responsibilities first.** Move result/data types, HP math,
   mode adapters, service orchestration, and drawing in separate steps. Leave
   forwarding exports in `renderer/nanoka/endgames.py`. Make drawing entirely
   synchronous and independent of a `NanokaClient` reference. Reuse one injected
   client per operation and test that only internally created clients are closed.
3. **Separate provider API access from domain clients.** Move Nanoka catalog,
   asset, version, and schedule operations behind a public API client. Move
   HoYoLAB request code under its provider without changing endpoint behavior.
   Wrap Prydwen fetchers without merging HTTP and browser transports. Update
   provider tests alongside each extraction; do not redesign network policies
   during file moves.
4. **Extract the main facade and remove import side effects.** Move
   `HonkaiStarrail` into `clients/main.py`, inject/lazily construct provider
   clients, preserve its existing delegates, and retain `client.py` imports.
   Root imports must not perform IO, discover writable paths, validate cookies,
   or open sessions. Keep the existing `PrydwenClient` API and sync/async
   distinctions intact.
5. **Split models, cache, and large renderers.** Move domain models into focused
   modules with stable re-exports. Separate manifest, JSON, and asset caching.
   Split skills/variants and Prydwen parsing/rendering by responsibility, then
   extract shared drawing and text utilities with matching behavior tests.
6. **Finish documentation and compatibility checks.** Document every public
   function, method, exported model/property, and provider API operation as it
   moves. Update README examples and package guidance after paths stabilize.
   Keep shims until an explicitly versioned compatibility decision removes them.

Keep each step reviewable and independently runnable. Avoid combining file moves
with behavior changes except where a contract regression demonstrates the need.

## Docstring contract

For each public/API function include a concise action summary and document:

- Arguments, defaults, accepted aliases, locale/version rules, and live/test
  date semantics where relevant.
- Return type and shape, including single versus multiple-season results and
  the distinction between provider data and image results.
- Expected exceptions and which missing-data conditions return empty results.
- Network/file/cache side effects, refresh behavior, session ownership, and
  async requirements.

Use the same format within each package; add a short example for ambiguous
entry points. Private helpers need a docstring when their calculation or
invariant is not obvious. Do not add meaningless parameter descriptions or
comments that repeat the function name.

## Verification gates

Run focused tests after each extraction, then the affected provider/renderer
suite, then the full offline suite. Require `compileall`, stable public imports,
and compatibility exports to pass before declaring a stage complete. Preserve
current caches and rendered filenames unless an intentional schema revision is
needed; status-sensitive endgame cache keys are already versioned.

PF regressions must preserve all three nodes, spawn counts, wave HP modifiers,
per-node elements, and the 99,000-point condition. AS regressions must preserve
two HP bars per reference boss, corrosion on additional targets, all node
buffs/mechanics, Starward mode, and its 10,200-point condition. Render assertions
must check text bounds, full descriptions, and image dimensions suitable for
Telegram. Check the approved info anchor at 1080x1440 and the comparison skills
anchor at 1920x3188 with eight tables. Network smoke tests are supplementary to
self-contained fixture tests.

## Deferred AA work

Do not implement AA floor cards in this refactor. Existing `PeakSchedule` data
has no dependable live date window; the SDK currently treats the highest ID as
current and consequently has no higher next ID. Preserve the explicit renderer
`NotImplementedError`. Incorporate the user's date-resolution fix in a later
version with tests for current/next selection before enabling AA cards.
