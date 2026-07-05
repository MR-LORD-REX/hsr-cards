from ..utils.elements import Elements
from ..utils.hsrfonts import HSRFonts
from PIL import Image, ImageDraw
from pathlib import Path
import asyncio

char_icon=Path(__file__).parent.parent / "assets" / "team" / "char_icon.png"
team_bg=Path(__file__).parent.parent / "assets" / "team" / "team_bg.png"
circle_mask=Path(__file__).parent.parent / "assets" / "team" / "circle.png"
ido_mask=Path(__file__).parent.parent / "assets" / "team" / "ido.png"
lvl_mask=Path(__file__).parent.parent / "assets" / "team" / "lvl.png"

async def get_icon(url:str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                from io import BytesIO
                from PIL import Image
                data = await response.read()
                return Image.open(BytesIO(data))
            
async def render(avatar:dict,team_full:Image.Image,offset_x:int,x:int):
    f=HSRFonts.get_font(9,"bold")
    f10=HSRFonts.get_font(10,"bold")
    
    ele=Elements.get_element(avatar['element'])
    ele=ele.resize((15,15))
    
    lvl=avatar['level']
    eidolon=avatar['rank']
    lvl=f"LvL.{lvl}"
    eld=f"{eidolon}" if eidolon>0 else "0"
    
    bg=Image.open(char_icon)
    bg=bg.resize((71,82))
    
    icon=await get_icon(avatar['icon'])
    icon=icon.resize((61,72))
    
    draw=ImageDraw.Draw(bg)
    
    bg.alpha_composite(icon,(5,1))
    
    circle=Image.open(circle_mask).convert("RGBA").resize((15,15))
    circle=Image.alpha_composite(circle,ele)
    bg.alpha_composite(circle,(3,3))
    
    bg.alpha_composite(Image.open(lvl_mask).convert("RGBA"),(0,73))
    bg.alpha_composite(Image.open(ido_mask).convert("RGBA"),(58,0))
    
    draw.text((18,73),lvl,font=f,fill=(255,255,255))
    draw.text((61,2),eld,font=f10,fill=(255,255,255))
    
    team_full.alpha_composite(bg,(offset_x+x*76,0))
    
            
async def render_team(team:list[dict])->Image.Image:
    team_full=Image.open(team_bg)
    offset_x=5
    tasks=[]
    for x,avatar in enumerate(team):
        tasks.append(render(avatar,team_full,offset_x,x))
    await asyncio.gather(*tasks)
    return team_full