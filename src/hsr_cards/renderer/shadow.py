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


class ASRenderer:
    def __init__(self):
        self.api = BaseAPI
        self.fonts = HSRFonts()
        self.floor_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "AS" / "floor_bg.png"
        self.floor_bg_tierce=Path(__file__).parent.parent / "assets" / "backgrounds" / "AS" / "floor_bg_tierce.png"
        self.buff_mask=Path(__file__).parent.parent / "assets" / "backgrounds" / "AS" / "buff_m.png"
        self.header_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "AS" / "header_bg.png"
        self.main_bg=Path(__file__).parent.parent / "assets" / "backgrounds" / "AS" / "main_bg.png"
        self.boss_mask=Path(__file__).parent.parent / "assets" / "backgrounds" / "AS" / "boss_m.png"
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
        
    async def _render_buff(self,buff: dict, draw: ImageDraw.ImageDraw ,main_img: Image.Image, i: int, f16: ImageFont.FreeTypeFont, col_width: int = 390):
        if buff:
            icon=await self.get_icon(buff["icon"])
            mask=Image.open(self.buff_mask)
            icon=icon.resize((36,36))
            mask.alpha_composite(icon,(0,0))
            main_img.alpha_composite(mask,(17+i*col_width,259))
            buff_name=buff["name_mi18n"]
            draw.text((58+i*(col_width+12),270),buff_name,font=f16,fill=(255,255,255,255))
            
    async def _render_team(self,team: list, main_img: Image.Image, i: int, col_width: int = 390):
        if team:
            team_img=await render_team(team)
            # For tierce (col_width=260): 230px wide; for standard (col_width=391): 310px wide
            team_w = 310 if col_width >= 390 else col_width - 30
            team_img=team_img.resize((team_w, 82))
            main_img.alpha_composite(team_img,(15+i*col_width,166))
        
        
    async def _render_floor(self,floor_data: dict) -> Image.Image | None:
        if floor_data['is_fast']:
            return None
        
        is_tierce = floor_data.get('is_tierce', False) and floor_data.get('node_3') is not None
        
        if is_tierce:
            main_img=Image.open(self.floor_bg_tierce).convert("RGBA")
        else:
            main_img=Image.open(self.floor_bg).convert("RGBA")
        
        draw=ImageDraw.Draw(main_img)
        f20=self.fonts.get_font(20, "bold")
        f16=self.fonts.get_font(16, "medium")

        name=floor_data["name"]
        draw.text((15,8),name,font=f20,fill=(255,255,255,255))
        
        t_score=0
        
        star_num=int(floor_data["star_num"])
        st=await render_stars(star_num)
        main_img.alpha_composite(st, (569,29))
        
        tasks=[]
        
        if is_tierce:
            # 3-team layout: 3 equal columns of 260px each
            col_width = 260
            node_count = 3
            time_x_offsets = [15, 275, 535]
            score_x_offsets = [15, 275, 535]
        else:
            col_width = 391
            node_count = 2
            time_x_offsets = [232, 590]
            score_x_offsets = [69, 469]
        
        for i in range(node_count):
            node=floor_data[f"node_{i+1}"]
            
            buff=node["buff"]
            tasks.append(self._render_buff(buff, draw, main_img, i, f16, col_width))
            
            challenge_time=node["challenge_time"]
            if challenge_time:
                challenge_time_str=f"{challenge_time['year']}/{challenge_time['month']}/{challenge_time['day']} {challenge_time['hour']}:{challenge_time['minute']}"
                draw.text((time_x_offsets[i],103),challenge_time_str,fill=(255,215,0),font=f16)
            
            team=node["avatars"]
            if team:
                tasks.append(self._render_team(team, main_img, i, col_width))
            
            score=int(node["score"])
            draw.text((score_x_offsets[i],137),f"{score}",font=f16,fill=(255,215,0,255))
            t_score+=score
        
        draw.text((114,59),f"{t_score}",font=f16,fill=(255,215,0,255))
        await asyncio.gather(*tasks)
        return main_img
    
    async def _render_header(self,data: dict) -> Image.Image | None:
        if not data['has_data'] :
            return None
        main_img=Image.open(self.header_bg).convert("RGBA")
        draw=ImageDraw.Draw(main_img)
        
        star_num=int(data["star_num"])
        battle_num=int(data["battle_num"])
        max_floor=data["max_floor"]
        
        f20=self.fonts.get_font(20, "bold")
        f16=self.fonts.get_font(16, "medium")
        
        draw.text((96,75), f"{star_num}", font=f20, fill=(255,215,0))
        draw.text((320,59), f"{max_floor}", font=f16, fill=(255,215,0))
        draw.text((344,94), f"{battle_num}", font=f16, fill=(255,215,0))
        
        group=data["groups"][0]
        upper=group["upper_boss"]
        lower=group["lower_boss"]
        tierce=group.get("tierce_boss")
        
        if tierce:
            # 3-boss layout: shift icons/names to fit all three
            boss_x_positions = [200, 450, 688]
            boss_name_x    = [35, 285, 535]
        else:
            boss_x_positions = [315, 688]
            boss_name_x    = [35, 410]
        
        bosses = [b for b in [upper, lower, tierce] if b is not None]
        boss_tasks = []
        
        async def _draw_boss(boss, icon_x, name_x):
            draw.text((name_x, 194), f"{boss['name_mi18n']}", font=f16, fill=(255,255,255))
            bm = Image.open(self.boss_mask).convert("RGBA")
            icon = await self.get_icon(boss["icon"])
            bm.alpha_composite(icon.resize((64,64)), (0,0))
            main_img.alpha_composite(bm, (icon_x, 173))
        
        for idx, boss in enumerate(bosses):
            boss_tasks.append(_draw_boss(boss, boss_x_positions[idx], boss_name_x[idx]))
        
        await asyncio.gather(*boss_tasks)
        return main_img
    
    async def render_AS(self,data: dict)-> Image.Image | None:
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
        y=327
        for floor_img in rendered_floors:
            if floor_img:
                main.alpha_composite(floor_img,(20,y))
                y+=floor_img.height+23
        main=main.crop((0,0,main.width,y))
        return main
        