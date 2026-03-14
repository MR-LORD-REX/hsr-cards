from hsr_cards import HonkaiStarrail
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

async def test():
    try:
        os.makedirs("Cards", exist_ok=True)
        async with HonkaiStarrail("800556377") as client:
            img=await client.anomaly()
            img.save(f"Cards/Anomaly.png")
            print(f"saved Cards/Anomaly.png")
            
            for i in range(1,3):
                img=await client.PF(schedule_type=str(i))
                img.save(f"Cards/PF_{i}.png")
                print(f"saved Cards/PF_{i}.png")
                
                img=await client.MOC(schedule_type=str(i))
                img.save(f"Cards/MOC_{i}.png")
                print(f"saved Cards/MOC_{i}.png")
                
                img=await client.shadow(schedule_type=str(i))
                img.save(f"Cards/AS_{i}.png")
                print(f"saved Cards/AS_{i}.png")
                
    except Exception as e:
        print(f"Error during test: {e}")
        pass

asyncio.run(test())