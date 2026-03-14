from .team import render_team
from .stars import render_stars
from ..api.base_api import BaseAPI
from PIL import Image, ImageDraw, ImageFont
from ..utils.hsrfonts import HSRFonts
from typing import Literal
from ..utils.errors import MOCDataError
from pathlib import Path
import asyncio

class MOCRenderer:
    def __init__(self):
        self.api = BaseAPI
        self.fonts = HSRFonts()
        self.floor_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "MOC" / "floor_bg.png"
        self.header_bg=Path(__file__).parent.parent / "assets"/"backgrounds"/"MOC"/"header_bg.png"
        self.main_bg=Path(__file__).parent.parent / "assets"/"backgrounds"/"MOC"/"main_bg.png"
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def _check_server(self,uid:str):
        if uid.startswith("1") or uid.startswith("8"):
            return 'prod_official_asia'
    
    async def _render_floor(self,floor_data: dict) -> Image.Image | None:
        if not floor_data['is_chaos'] or floor_data['is_fast']:
            return None
        main_img=Image.open(self.floor_bg).convert("RGBA")
        draw=ImageDraw.Draw(main_img)
        f24=self.fonts.get_font(24, "bold")
        f16=self.fonts.get_font(16, "light")
        f14=self.fonts.get_font(14, "light")
        name=floor_data["name"]
        round_num=floor_data["round_num"]
        draw.text((15,17), f"{name}" ,font=f24, fill=(255,255,255))
        draw.text((120,56), f"{round_num}", font=f16, fill=(255,255,255))
        t=[]
        teams=[]
        for node in ["node_1", "node_2"]:
            team_data = floor_data[node]["avatars"]
            t.append(render_team(team_data))
        i1,i2=await asyncio.gather(*t)
        teams.append(i1.resize((353,94)))
        teams.append(i2.resize((353,94)))
        for i, team in enumerate(teams):
            main_img.alpha_composite(team, (15+i*391, 152))
            time=floor_data[f"node_{i+1}"]["challenge_time"]
            time=f"{time['year']}/{time['month']}/{time['day']} {time['hour']}:{time['minute']}"
            draw.text((125+i*392, 127), time, font=f14, fill=(255,255,255))
        stars=await render_stars(floor_data["star_num"])
        main_img.alpha_composite(stars, (570,29))
        return main_img
    
    async def _render_header(self,data: dict) -> Image.Image:
        main_img=Image.open(self.header_bg).convert("RGBA")
        draw=ImageDraw.Draw(main_img)
        star_num=data["star_num"]
        battle_num=data["battle_num"]
        max_floor=data["max_floor"]
        f20=self.fonts.get_font(20, "bold")
        f16=self.fonts.get_font(16, "light")
        draw.text((96,75), f"{star_num}", font=f20, fill=(255,255,255))
        draw.text((314,59), f"{max_floor}", font=f16, fill=(255,255,255))
        draw.text((344,94), f"{battle_num}", font=f16, fill=(255,255,255))
        return main_img
    
    async def render_moc(self,data: dict)-> Image.Image:
        if data["retcode"] != 0:
            raise MOCDataError("Invalid MOC data",code=data["retcode"])
        elif not data["data"]["all_floor_detail"]:
            raise MOCDataError("No floor data available",code=10104)
        elif not data["data"]["has_data"]:
            raise MOCDataError("No MOC data available")
        head=data["data"]
        main=Image.open(self.main_bg).convert("RGBA")
        header_img=await self._render_header(head)
        floors=data["data"]["all_floor_detail"]
        t=[]
        rendered_floors=[]
        for floor in floors:
            t.append(self._render_floor(floor))
        try:
            rendered_floors=await asyncio.gather(*t)
            if not rendered_floors:
                main=main.crop((0,0,main.width,188))
                main.alpha_composite(header_img, (20,25))
                return main
            else:
                main.alpha_composite(header_img, (20,25))
                y=188
                for i, floor_img in enumerate(rendered_floors):
                    if floor_img:
                        main.alpha_composite(floor_img, (20,y))
                        y+=floor_img.height+23
                return main
        except Exception as e:
            raise MOCDataError(f"Error rendering MOC data: {e}")