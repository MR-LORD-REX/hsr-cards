from ..api.base_api import BaseAPI
from .team import render_team 
from .stars import render_stars
from ..utils.hsrfonts import HSRFonts
from ..utils.errors import PFError
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import asyncio
import aiohttp
from io import BytesIO


class PFRenderer:
    def __init__(self):
        self.api = BaseAPI
        self.fonts = HSRFonts()
        self.floor_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "PF" / "floor_bg.png"
        self.buff_mask=Path(__file__).parent.parent / "assets" / "backgrounds" / "PF" / "buff_m.png"
        self.header_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "PF" / "header_bg.png"
        self.main_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "PF" / "main_bg.png"
        self.session = aiohttp.ClientSession()
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def get_icon(self, url: str):
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(BytesIO(data)).convert("RGBA")
        except Exception as e:
            print(f"Error fetching icon: {e}")
            return Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    
    def _check_server(self,uid:str):
        if uid.startswith("1") or uid.startswith("8"):
            return 'prod_official_asia'
        
    async def _render_buff(self,buff: dict, draw: ImageDraw.ImageDraw ,main_img: Image.Image, i: int, f16: ImageFont.FreeTypeFont):
        if buff:
            icon=await self.get_icon(buff["icon"])
            mask=Image.open(self.buff_mask)
            icon=icon.resize((36,36))
            mask.alpha_composite(icon,(0,0))
            main_img.alpha_composite(mask,(17+i*390,259))
            buff_name=buff["name_mi18n"]
            draw.text((58+i*402,270),buff_name,font=f16,fill=(255,255,255,255))
            
    async def _render_team(self,team: list, main_img: Image.Image, i: int):
        if team:
            team_img=await render_team(team)
            team_img=team_img.resize((310,82))
            main_img.alpha_composite(team_img,(15+i*391,166))
        
        
    async def _render_floor(self,floor_data: dict) -> Image.Image | None:
        if floor_data['is_fast']:
            return None
        main_img=Image.open(self.floor_bg).convert("RGBA")
        draw=ImageDraw.Draw(main_img)
        f20=self.fonts.get_font(20, "bold")
        f16=self.fonts.get_font(16, "medium")

        name=floor_data["name"]
        draw.text((15,8),name,font=f20,fill=(255,255,255,255))
        
        round_num=floor_data["round_num"]
        draw.text((114,59),f"{round_num}",font=f16,fill=(255,215,0,255))
        
        t_score=0
        
        star_num=floor_data["star_num"]
        st=await render_stars(star_num)
        main_img.alpha_composite(st, (569,29))
        
        tasks=[]
        
        for i in range(2):
            node=floor_data[f"node_{i+1}"]
            
            buff=node["buff"]
            tasks.append(self._render_buff(buff, draw, main_img, i, f16))
            
            challenge_time=node["challenge_time"]
            challenge_time=f"{challenge_time['year']}/{challenge_time['month']}/{challenge_time['day']} {challenge_time['hour']}:{challenge_time['minute']}"
            draw.text((232+i*358,103),challenge_time,fill=(255,215,0),font=f16)
            
            team=node["avatars"]
            if team:
                tasks.append(self._render_team(team, main_img, i))
            
            score=int(node["score"])
            draw.text((69+i*400,137),f"{score}",font=f16,fill=(255,215,0,255))
            t_score+=score
        draw.text((259,59),f"{t_score}",font=f16,fill=(255,215,0,255))
        await asyncio.gather(*tasks)
        return main_img
    
    async def _render_header(self,data: dict) -> Image.Image | None:
        if not data['has_data'] :
            return None
        main_img=Image.open(self.header_bg).convert("RGBA")
        draw=ImageDraw.Draw(main_img)
        star_num=data["star_num"]
        battle_num=data["battle_num"]
        max_floor=data["max_floor"]
        f20=self.fonts.get_font(20, "bold")
        f16=self.fonts.get_font(16, "medium")
        draw.text((96,75), f"{star_num}", font=f20, fill=(255,215,0))
        draw.text((320,59), f"{max_floor}", font=f16, fill=(255,215,0))
        draw.text((344,94), f"{battle_num}", font=f16, fill=(255,215,0))
        return main_img
    
    async def render_pf(self,data: dict)-> Image.Image | None:
        if data["retcode"] != 0:
            raise PFError("Invalid PF data",code=data["retcode"])
        elif not data["data"]["all_floor_detail"]:
            raise PFError("No floor data available",code=10104)
        head=data["data"]
        main=Image.open(self.main_bg).convert("RGBA")
        header_img=await self._render_header(head)
        if header_img:
            main.alpha_composite(header_img,(20,23))
        else:
            raise PFError("NOT attempted PF yet")
        floor_data=data["data"]["all_floor_detail"]
        t=[]
        for floor in floor_data:
            t.append(self._render_floor(floor))
        rendered_floors=await asyncio.gather(*t)
        y=188
        for floor_img in rendered_floors:
            if floor_img:
                main.alpha_composite(floor_img,(20,y))
                y+=floor_img.height+23
        main=main.crop((0,0,main.width,y))
        return main
        