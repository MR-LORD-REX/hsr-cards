# Prydwen builds and tier lists

Prydwen features need neither a player UID nor HoYoLAB cookies. The query client reads tier/code data, while its build workflow fetches source pages, writes reviewable drafts, and renders approved or explicitly requested preview cards.

## Published build cards

```python
from hsr_cards import HonkaiStarrail

async with HonkaiStarrail() as client:
    await client.update_builds()
    image = await client.character_build("Acheron")
    if image is not None:
        image.save("acheron-build.png")

    link = await client.character_build("Acheron", url=True)
    print(link)
```

Generated build cards are downloaded from GitHub rather than bundled with the PyPI package. Run `update_builds()` before the first lookup, and again whenever you want the current repository cards. Installed packages store them in `.hsr_cards_builds/` under your application's working directory; source checkouts retain their existing `src/hsr_cards/assets/char_builds/` tree. Downloads create missing directories and refresh every indexed variant and condition page. Local-only cards are retained; a failed download does not replace the previous metadata.

`character_build()` resolves an identifier or Nanoka catalog filters. A single clean match returns one image/link. Missing build variants return `None`. `detailed=True` returns a list containing a summary and its condition pages.

Use the same explicit directory for downloads and later lookups when your application changes working directories:

```python
from hsr_cards import HonkaiStarrail

async with HonkaiStarrail() as client:
    await client.update_builds(build_dir="data/builds")
    image = await client.character_build("Acheron", build_dir="data/builds")
    if image is not None:
        image.save("acheron-build.png")
```

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

The default working directory is the nearest existing ancestor `.hsr_prydwen` tree, or `.hsr_prydwen` under the caller's working directory when none exists. It contains `raw`, `data`, `cards`, and reports. Approved publication uses the same default build directory as downloaded cards: existing source-checkout build assets or `.hsr_cards_builds/` for an installed package. `build_dir`, `nanoka_cache`, and `nanoka_version` are explicit constructor options.

```bash
hsr-prydwen --help
hsr-prydwen --nanoka-version 4.7.51 pull acheron
hsr-prydwen --nanoka-version 4.7.51 parse acheron
```

See [PrydwenClient reference](../api/prydwen-client.md), [Prydwen models](../api/prydwen-models.md), and [demo outputs](../showcase.md#build-card).
