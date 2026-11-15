# Character and equipment cards

Render Nanoka character information, skills, Light Cones, relic sets, and items without a player account. Every request resolves the selected build and downloads only the assets it needs.

## Character information

```python
from hsr_cards import get_character_info

card = await get_character_info(1507, version="4.7.51", locale="en")
card.save("character-info.png")
print(card.character, card.version, card.cache_path)
```

`InfoCardResult` carries `image`, `character`, `version`, and `cache_path`. It forwards PIL image attributes such as `size` and `width`, and exposes `save()`.

## Skills and rich messages

```python
import json
from hsr_cards import get_character_skills

skills = await get_character_skills(1511, version="4.6.54")
skills.save("character-skills.png")
payload = skills.to_json_dict()
print(json.dumps(payload, ensure_ascii=False))
```

`SkillsCardResult` contains `image`, `tables`, `dropdowns`, `table_models`, and `sections`. `dropdowns` maps each label to an index in `tables`. `sections` groups skills, eidolons, and material descriptions. The result does not expose character/version metadata or forward arbitrary image attributes; use `skills.image.size` to inspect dimensions.

## Compare two builds

```python
comparison = await get_character_skills(
    1511,
    version=("4.6.51", "4.6.54"),
)
comparison.save("character-skills-comparison.png")
```

Pass the older build first. One version produces a normal card; two produce inline differences. More than two builds raises `ValueError`. Added descriptions are highlighted, removed text is struck through, and tables retain old-to-new values.

## Light Cones, relics, and items

```python
from hsr_cards import get_LC_info, get_relic_info, get_item_info

light_cone = await get_LC_info(23066, version="4.7.51")
light_cone.save("light-cone-info.png")

relic = await get_relic_info(134, version="4.7.51")
relic.save("relic-set-info.png")

item = await get_item_info(223, version="4.7.51")
item.save("item-info.png")
```

The exact capitalization of `get_LC_info` is part of the public API. Light Cone cards show level-80 base stats and inline S1-S5 values. Relic cards include the set's pieces and bonuses. Item cards include descriptions and acquisition sources. Their result objects expose localized metadata alongside the image.

## Batch rendering

```python
from hsr_cards import render_all_info

batch = await render_all_info(
    version="4.7.51",
    identifiers=[1507, 1511],
    concurrency=2,
)
for item in batch.succeeded:
    item.result.save(f"character-{item.identifier}.png")
for identifier, error in batch.errors.items():
    print(identifier, str(error))
```

Omit `identifiers` to list the provider catalog. `render_all_info()` and `render_all_skills()` always rerender their selected characters and replace matching rendered caches. Ordinary per-character failures are stored in the batch; cancellation propagates to the caller.

## Cache controls

Standalone card functions accept `force_refresh=True` to bypass a rendered image read. `use_rendered_cache=False` disables generated-image caching, while downloaded data and artwork may still be cached. Facade methods expose their own signatures: do not assume every standalone keyword is accepted by every facade delegate.

See [card function signatures](../api/card-functions.md), [result properties](../api/results.md), [cache behavior](caching.md), and [demo outputs](../showcase.md#character-info).
