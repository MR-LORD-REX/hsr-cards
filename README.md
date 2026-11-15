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

See the [quickstart](docs/getting-started/quickstart.md), [endgame guide](docs/guides/endgame.md), [player cards](docs/guides/player-cards.md), and [GitHub Pages setup](docs/guides/github-pages.md). The documentation tracks the current source checkout; published package versions may have an older API.

[MIT license](LICENSE) · [Report an issue](https://github.com/MR-LORD-REX/hsr-cards/issues)

A community project independent of HoYoverse, Nanoka, and Prydwen.
