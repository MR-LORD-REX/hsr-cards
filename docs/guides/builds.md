# Prydwen builds and tier lists

Prydwen features need neither a player UID nor HoYoLAB cookies. The query client reads tier/code data, while its build workflow fetches source pages, writes reviewable drafts, and renders approved or explicitly requested preview cards.

## Published build cards

```python
from hsr_cards import HonkaiStarrail

async with HonkaiStarrail() as client:
    image = await client.character_build("Acheron")
    if image is not None:
        image.save("acheron-build.png")

    link = await client.character_build("Acheron", url=True)
    print(link)
```

`character_build()` resolves an identifier or Nanoka catalog filters. A single match returns one image/link; several return a list. Missing build variants return `None`. `detailed=True` selects a summary and its condition pages. `update_builds()` refreshes bundled community images from repository metadata.

## Tiers and active codes

```python
from hsr_cards import HonkaiStarrail

async with HonkaiStarrail() as client:
    image, data = await client.tier_list("MOC", raw=True)
    image.save("memory-of-chaos-tiers.png")
    print(data.mode, data.mode_key)
    for code in await client.redeem_codes():
        print(code.code, [(reward.name, reward.count) for reward in code.rewards])
```

Tier modes accept MOC/PF/AS aliases; timeout values are seconds. Code queries return `RedeemCode`/`Reward` objects and do not generate a card.

## Build collection and review

```python
from hsr_cards import PrydwenClient

async with PrydwenClient(nanoka_version="4.7.51") as client:
    await client.urls()
    await client.pull("acheron")
    client.parse("acheron")
    checks = client.validate(client.data_dir / "acheron.json")
    print(checks)
    # Review the draft and its validation results before explicitly approving it.
    client.approve("acheron", reviewer="your-name")
    output = client.card("acheron")
    print(output)
```

`urls()` and `pull()` are asynchronous collection operations. `parse()`, `validate()`, `approve()`, `approve_all()`, `teams()`, `card()`, and `cards()` use local files synchronously. Parsing needs matching local Nanoka catalogs. The default HTTP collector can be replaced with `transport="browser"` after installing the browser extra. Set `chrome=` to the installed browser executable; the default points to Windows Google Chrome.

Drafts are excluded from normal rendering. `allow_draft=True` creates a preview while retaining draft state. Approved cards are also written to `build_dir`; temporary reports/contact sheets belong outside it. `exclude_extra=True` makes a clean build card, while `False` includes detailed conditions. A render can produce condition pages as well as its main PNG.

## Files and CLI

The default working directory is the nearest existing ancestor `.hsr_prydwen` tree, or `.hsr_prydwen` under the caller's working directory when none exists. It contains `raw`, `data`, `cards`, and reports. `build_dir`, `nanoka_cache`, and `nanoka_version` are explicit constructor options.

```bash
hsr-prydwen --help
hsr-prydwen --nanoka-version 4.7.51 pull acheron
hsr-prydwen --nanoka-version 4.7.51 parse acheron
```

See [PrydwenClient reference](../api/prydwen-client.md), [Prydwen models](../api/prydwen-models.md), and [demo outputs](../showcase.md#build-card).
