# Versions, caching, and ownership

Provider data and rendered images have separate caches. Choose the root directory explicitly when your application runs from several working directories, containers, or background jobs.

## Nanoka data and assets

The default downloaded cache is `.nanoka_cache` under the caller's working directory:

```text
.nanoka_cache/
  manifest.json
  <version>/
    <locale>/
      data/
      assets/
```

`NanokaClient(version=None)` resolves the latest published build. `include_assets=True` is the domain-client default; use `False` when you want targeted queries rather than bulk artwork downloads. Card loaders select targeted assets independently.

```python
from hsr_cards import NanokaClient

async with NanokaClient(cache_dir="data/nanoka", include_assets=False) as client:
    versions = await client.get_versions()
    print(versions.latest, versions.live_server, versions.live_beta)
    await client.update_assets(version=versions.latest)
    # Explicit cache invalidation, if requested by your application:
    # await client.clear_cache(version=versions.latest)
```

`update_assets(version=...)` validates the published version before switching the client and refreshing the cache. Omitting `version` refreshes the active build. `clear_cache(version=...)` removes one version; omitting the argument clears all downloaded versions and the global manifest. These are filesystem operations, rather than card renders.

## Rendered images

The default image cache is `.hsr_cards_rendered`. Non-player card filenames include the identity, card family, and selected build. Comparisons include both builds separated by `--`; non-English output adds a locale suffix.

Standalone card functions accept `rendered_cache_dir`, `use_rendered_cache`, and `force_refresh`. A rendered-image hit does not promise that all provider metadata can be skipped. Skills payloads are rebuilt even when the image itself is reused. Endgame cache identities also include schedule status.

- `force_refresh=True` skips a generated-image read.
- `use_rendered_cache=False` disables generated-image read/write activity.
- Downloaded catalogs and artwork may still be read, requested, or cached.
- Batch info/skills calls always rerender and replace matching images when caching is enabled.

Player images and Prydwen working outputs keep their own paths; they are not redirected into the Nanoka rendered-image cache.

## Locale selection

The published locale values are `en`, `zh`, `ja`, and `ko`. `Locale.normalize()` accepts supported aliases and raises `ValueError` for an unknown locale. Each provider cache is locale-specific.

An initialized Nanoka client injected into an endgame render keeps its own language/cache/proxy configuration. Its language determines the rendered-cache suffix, even when the render function's `locale` argument uses its default.

## Resource ownership

```python
from hsr_cards import HonkaiStarrail, NanokaClient

async with NanokaClient(language="en", include_assets=False) as nanoka:
    await nanoka.initialize()
    async with HonkaiStarrail(nanoka_client=nanoka) as facade:
        card = await facade.get_current_endgame_card("PF", floors=4)
    # The facade did not close nanoka: its surrounding context still owns it.
```

The facade and provider clients close only resources they construct. An injected client, API client, cache transport, or HTTP session remains caller-owned. Close owned resources with an async context or `await close()`; cancellation and failed loads should still reach cleanup.

See [NanokaClient](../api/nanoka-client.md), [provider APIs](../api/provider-apis.md), and [result objects](../api/results.md).
