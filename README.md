# HSR Cards

An async Python library for Honkai: Star Rail character, equipment, endgame, and player cards, with independent Nanoka, Prydwen, and HoYoLAB clients. Requires Python 3.10+.

[Documentation website](https://mr-lord-rex.github.io/hsr-cards/) · [Documentation index](docs/readme.md) · [API reference](docs/api/main-client.md) · [Card showcase](docs/showcase.md)

Install the current repository in your virtual environment:

```bash
git clone https://github.com/MR-LORD-REX/hsr-cards.git
cd hsr-cards
python -m pip install -e .
```

```python
import asyncio
from hsr_cards import HonkaiStarrail

async def main():
    async with HonkaiStarrail() as client:
        card = await client.get_character_info(1507, version="4.7.51")
        card.save("character-info.png")

asyncio.run(main())
```

Game sprite paths normalize Windows and POSIX separators before icon lookup. English cards fall back to bundled DIN fonts when optional system fonts are missing or unreadable. Chinese, Japanese, and Korean Nanoka cards also look for installed Noto CJK or macOS language fonts; install a suitable CJK font for full character coverage.

Optional Prydwen browser collection discovers installed Chrome/Chromium on Windows, Linux, and macOS. If none is found, it uses Playwright's managed Chromium. Install the browser extra and managed browser when needed:

```bash
python -m pip install "hsr-cards[browser]"
python -m playwright install chromium
```

An explicit `chrome=` or `--chrome` path overrides discovery.

See the [quickstart](docs/getting-started/quickstart.md), [endgame guide](docs/guides/endgame.md), [player cards](docs/guides/player-cards.md). The documentation tracks the current source checkout; published package versions may have an older API.

[MIT license](LICENSE) · [Report an issue](https://github.com/MR-LORD-REX/hsr-cards/issues)

A community project independent of HoYoverse, Nanoka, and Prydwen.
