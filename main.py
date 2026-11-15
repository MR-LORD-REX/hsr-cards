import asyncio
import os
from pathlib import Path
import sys
from dotenv import load_dotenv

# Load the local source tree under the same package name used by installed builds.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

load_dotenv()
from hsr_cards import HonkaiStarrail, NanokaClient, PrydwenClient
from hsr_cards.models.auth import Cookies


UID = 800556377 

proxy = None  # Optional: Set your proxy here if needed

os.makedirs("Cards",exist_ok=True)

async def main():
    # async with NanokaClient() as n :
    #     c = await n.get_character("yao")
    #     print(c)

    # prydwen = PrydwenClient()
    # await prydwen.urls()
    # await prydwen.pull()
    # cards =  prydwen.cards()



    async with HonkaiStarrail(uid=UID, cookie=None,proxy=proxy) as client:
        cards = await client.get_current_endgame_card(game_mode="AS",floors=[4])
        for c in cards.cards:
            print(f"[*] Rendering {c.name}...")
            c.image.show()

    #     print("[*] Rendering Banners...")
    #     img = await client.banners()
    #     img.save("Cards/banners.png")
    #     print("[OK] Banners saved -> Cards/banners.png")

    #     print("[*] Rendering Events...")
    #     img = await client.events()
    #     img.save("Cards/events.png")
    #     print("[OK] Events saved -> Cards/events.png")

    #     print("[*] Rendering Endgame Modes...")
    #     img = await client.endgame()
    #     img.save("Cards/endgame.png")
    #     print("[OK] Endgame saved -> Cards/endgame.png")

    #     # print("[*] Rendering Notes...")
    #     # img = await client.notes()
    #     # img.save("Cards/notes.png")
    #     # print("[OK] Notes saved -> Cards/notes.png")

    #     print("[*] Fetching MOC...")
    #     img = await client.MOC(schedule_type="1")
    #     img.save("Cards/moc.png")
    #     print("[OK] MOC saved -> Cards/moc.png")

    #     print("[*] Fetching Pure Fiction...")
    #     img = await client.PF(schedule_type="1")
    #     img.save("Cards/pf.png")
    #     print("[OK] PF saved  -> Cards/pf.png")

    #     # print("[*] Fetching Apocalyptic Shadow...")
    #     # img = await client.shadow(schedule_type="1")
    #     # img.save("Cards/shadow.png")
    #     # print("[OK] Shadow saved -> Cards/shadow.png")

    #     # print("[*] Fetching Anomaly...")
    #     # img = await client.anomaly()
    #     # img.save("Cards/anomaly.png")
    #     # print("[OK] Anomaly saved -> Cards/anomaly.png")


if __name__ == "__main__":
    asyncio.run(main())
