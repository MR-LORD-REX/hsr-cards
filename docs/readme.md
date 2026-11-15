# HSR Cards documentation

HSR Cards is an async Python library for Honkai: Star Rail images and provider data. Render character and equipment cards, current and upcoming endgame floors, player records, and community build cards. Use the main facade or independent Nanoka, Prydwen, and HoYoLAB clients.

Read these pages in the [documentation website](index.html) or directly as Markdown. The reference describes the current repository; a published PyPI release may expose an older API.

## Get started

- [Installation](getting-started/installation.md): Python requirements, source installation, and optional browser support.
- [Quickstart](getting-started/quickstart.md): render your first card and query a provider.
- [Card showcase](showcase.md): example outputs, their public methods, and data sources.

## Usage guides

- [Character and equipment cards](guides/characters.md): information, skills, Light Cones, relics, items, comparisons, and batches.
- [Endgame floor cards](guides/endgame.md): live and upcoming MOC, PF, and AS floors.
- [Player cards](guides/player-cards.md): HoYoLAB records, notes, banners, events, and Currency Wars.
- [Builds and tier lists](guides/builds.md): community cards and the Prydwen build workflow.
- [Caching](guides/caching.md): provider data, generated images, refreshing, and resource ownership.
- [GitHub Pages](guides/github-pages.md): build, preview, validate, and publish this documentation.

## Public API

- [HonkaiStarrail](api/main-client.md): the main facade's public methods and properties.
- [NanokaClient](api/nanoka-client.md): versioned catalogs, domain queries, and assets.
- [PrydwenClient](api/prydwen-client.md): tier lists, codes, build collection, and rendered drafts.
- [HoYoLABClient](api/hoyolab-client.md): validated player and account queries.
- [Standalone card functions](api/card-functions.md): package-root rendering functions and batch operations.
- [Provider APIs](api/provider-apis.md): transport access, cache objects, and owned sessions.
- [Card results](api/results.md): image wrappers, metadata, navigation, and batch failures.
- [Cache API](api/cache.md): manifests, downloaded assets, and cache management.
- [Errors and compatibility](api/errors.md): exceptions and supported import paths.

### Models and properties

- [Nanoka models](api/nanoka-models.md): catalog fields, domain wrappers, and schedule dates.
- [HoYoLAB models](api/hoyolab-models.md): battle records, notes, Currency Wars, and explicit credentials.
- [Prydwen models](api/prydwen-models.md): tier lists, redeem codes, builds, and validation results.

### Nanoka query families

- [Characters](api/nanoka/characters.md)
- [Light Cones and relics](api/nanoka/equipment.md)
- [Monsters and stages](api/nanoka/monsters.md)
- [Schedules and bosses](api/nanoka/schedules.md)
- [Items and Currency Wars](api/nanoka/items-currency.md)
- [Assets and cache](api/nanoka/assets.md)

## Project links

[Repository](https://github.com/MR-LORD-REX/hsr-cards) · [Issues](https://github.com/MR-LORD-REX/hsr-cards/issues) · [MIT license](https://github.com/MR-LORD-REX/hsr-cards/blob/main/LICENSE)

This community library is independent of HoYoverse, Nanoka, and Prydwen. Nanoka Anomaly Arbitration floor cards remain deferred; the existing HoYoLAB `anomaly()` player renderer is documented separately.
