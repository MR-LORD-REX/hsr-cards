# Quickstart

Start with a character card. Nanoka and Prydwen features work without a player UID or HoYoLAB credentials.

```python
import asyncio
from hsr_cards import get_character_info

async def main():
    card = await get_character_info(1507, version="4.7.51")
    card.save("character-info.png")
    print(card.character, card.version, card.image.size)

asyncio.run(main())
```

A numeric Nanoka ID or published name identifies the character. A pinned version makes the request repeatable; omitting it selects the newest published Nanoka build.

## Use the convenience client

```python
import asyncio
from hsr_cards import HonkaiStarrail

async def main():
    async with HonkaiStarrail() as client:
        card = await client.get_current_endgame_card("PF", floors=4)
        card.cards[0].save("pure-fiction-floor4.png")

asyncio.run(main())
```

`HonkaiStarrail` delegates to independent provider clients. A UID is required only when you request player data. Its context closes the provider resources it creates; injected clients remain caller-owned.

## Read provider data

```python
from hsr_cards import NanokaClient

async def lookup():
    async with NanokaClient(language="en", include_assets=False) as client:
        await client.initialize()
        character = await client.get_character(name="Acheron")
        if character is not None:
            print(character.id, character.display_name())
```

Provider query objects contain summaries and details. They are different from rendered card results.

## Player cards

Pass explicit credentials for player features. The application chooses where to obtain them:

```python
import os
from hsr_cards import HonkaiStarrail
from hsr_cards.models.auth import Cookies

async def player_card():
    cookie = Cookies(
        ltoken_v2=os.environ["ltoken_v2"],
        ltuid_v2=os.environ["ltuid_v2"],
    )
    async with HonkaiStarrail("800556377", cookie=cookie) as client:
        image = await client.MOC(schedule_type="1")
        image.save("player-moc.png")
```

The package does not load `.env` automatically. If your application uses python-dotenv, call `load_dotenv()` before reading the environment. [Player cards](../guides/player-cards.md) explains credentials, regions, and return values.

Next: [character cards](../guides/characters.md), [endgame floors](../guides/endgame.md), or [API reference](../api/main-client.md).
