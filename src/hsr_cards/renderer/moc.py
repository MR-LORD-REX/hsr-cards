from .team import render_team
from .stars import render_stars
from ..api.base_api import BaseAPI
from PIL import Image, ImageDraw, ImageFont
from ..utils.hsrfonts import HSRFonts
from typing import Literal
from ..utils.errors import MOCDataError
from pathlib import Path
import asyncio

_ASSETS = Path(__file__).parent.parent / "assets"

class MOCRenderer:
    def __init__(self):
        self.api = BaseAPI
        self.fonts = HSRFonts()
        self.floor_bg  = _ASSETS / "backgrounds" / "MOC" / "floor_bg.png"
        self.floor_bg3 = _ASSETS / "backgrounds" / "MOC" / "floor_bg3.png"
        self.header_bg = _ASSETS / "backgrounds" / "MOC" / "header_bg.png"
        self.main_bg   = _ASSETS / "backgrounds" / "MOC" / "main_bg.png"
        self.prism_star = _ASSETS / "general" / "prism_star.png"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _check_server(self, uid: str):
        if uid.startswith("1") or uid.startswith("8"):
            return 'prod_official_asia'

    async def _render_floor(self, floor_data: dict) -> Image.Image | None:
        if not floor_data['is_chaos'] or floor_data['is_fast']:
            return None

        is_tierce = floor_data.get("is_tierce", False) and floor_data.get("node_3") is not None

        if is_tierce:
            return await self._render_floor_3team(floor_data)
        else:
            return await self._render_floor_2team(floor_data)

    async def _render_floor_2team(self, floor_data: dict) -> Image.Image:
        """Original 2-team layout, unchanged logic."""
        main_img = Image.open(self.floor_bg).convert("RGBA")
        draw = ImageDraw.Draw(main_img)
        f24 = self.fonts.get_font(24, "bold")
        f16 = self.fonts.get_font(16, "light")
        f14 = self.fonts.get_font(14, "light")

        name = floor_data["name"]
        round_num = floor_data["round_num"]
        draw.text((15, 17), f"{name}", font=f24, fill=(255, 255, 255))
        draw.text((120, 56), f"{round_num}", font=f16, fill=(255, 255, 255))

        t = [render_team(floor_data["node_1"]["avatars"]),
             render_team(floor_data["node_2"]["avatars"])]
        i1, i2 = await asyncio.gather(*t)

        teams = [i1.resize((353, 94)), i2.resize((353, 94))]
        for i, team in enumerate(teams):
            main_img.alpha_composite(team, (15 + i * 391, 152))
            time = floor_data[f"node_{i + 1}"]["challenge_time"]
            time_str = f"{time['year']}/{time['month']:02d}/{time['day']:02d} {time['hour']:02d}:{time['minute']:02d}"
            draw.text((125 + i * 392, 127), time_str, font=f14, fill=(255, 255, 255))

        stars = await render_stars(floor_data["star_num"])
        main_img.alpha_composite(stars, (570, 29))
        return main_img

    async def _render_floor_3team(self, floor_data: dict) -> Image.Image:
        main_img = Image.open(self.floor_bg3).convert("RGBA")
        draw = ImageDraw.Draw(main_img)
        f20 = self.fonts.get_font(20, "bold")
        f14 = self.fonts.get_font(14, 'bold')
        f13 = self.fonts.get_font(13, 'bold')

        name = floor_data["name"]
        round_num = floor_data["round_num"]

        draw.text((15, 17), f"{name}", font=f20, fill=(255, 255, 255))
        draw.text((80, 60), f"{round_num}", font=f14, fill=(255, 255, 255))
        SLOT_X = [8, 263, 530]
        TEAM_W = 238
        TEAM_H = 94
        TEAM_Y = 148

        LABEL_X = [80, 340, 600]

        nodes = ["node_1", "node_2", "node_3"]
        tasks = [render_team(floor_data[node]["avatars"]) for node in nodes]
        team_imgs = await asyncio.gather(*tasks)

        labels = ["Team Setup 1", "Team Setup 2", "Team Setup 3"]
        f12 = self.fonts.get_font(12, "bold")

        for i, (team_img, lx) in enumerate(zip(team_imgs, LABEL_X)):
            draw.text((SLOT_X[i] + 4,108), labels[i], font=f12, fill=(255, 255, 255))

        for i, (team_img, sx) in enumerate(zip(team_imgs, SLOT_X)):
            resized = team_img.resize((TEAM_W, TEAM_H))
            main_img.alpha_composite(resized, (sx, TEAM_Y))

            # Challenge time per node
            node_key = nodes[i]
            time = floor_data[node_key]["challenge_time"]
            time_str = f"{time['year']}/{time['month']:02d}/{time['day']:02d} {time['hour']:02d}:{time['minute']:02d}"
            draw.text((SLOT_X[i] + 4, 130), time_str, font=f13, fill=(200, 200, 200))

        stars = await render_stars(floor_data["star_num"])
        main_img.alpha_composite(stars, (570, 29))

        if floor_data.get("extra_star_num", 0) > 0:
            prism = Image.open(self.prism_star).convert("RGBA")
            prism = prism.resize((28, 28), Image.LANCZOS)
            # Place just to the right of regular stars
            main_img.alpha_composite(prism, (735, 32))

        return main_img

    async def _render_header(self, data: dict) -> Image.Image:
        main_img = Image.open(self.header_bg).convert("RGBA")
        draw = ImageDraw.Draw(main_img)
        star_num  = data["star_num"]
        battle_num = data["battle_num"]
        max_floor  = data["max_floor"]
        extra_star_num = data.get("extra_star_num", 0)

        f20 = self.fonts.get_font(20, "bold")
        f16 = self.fonts.get_font(16, "light")

        draw.text((96, 75), f"{star_num}", font=f20, fill=(255, 255, 255))
        draw.text((314, 59), f"{max_floor}", font=f16, fill=(255, 255, 255))
        draw.text((344, 94), f"{battle_num}", font=f16, fill=(255, 255, 255))

        if extra_star_num > 0:
            prism = Image.open(self.prism_star).convert("RGBA")
            prism = prism.resize((32, 32), Image.LANCZOS)
            main_img.alpha_composite(prism, (148, 65))

        return main_img

    async def render_moc(self, data: dict) -> Image.Image:
        if data["retcode"] != 0:
            raise MOCDataError("Invalid MOC data", code=data["retcode"])
        elif not data["data"]["all_floor_detail"]:
            raise MOCDataError("No floor data available", code=10104)
        elif not data["data"]["has_data"]:
            raise MOCDataError("No MOC data available")

        head = data["data"]
        main = Image.open(self.main_bg).convert("RGBA")

        header_img = await self._render_header(head)
        floors = data["data"]["all_floor_detail"]

        tasks = [self._render_floor(floor) for floor in floors]
        try:
            rendered_floors = await asyncio.gather(*tasks)
            if not any(rendered_floors):
                main = main.crop((0, 0, main.width, 188))
                main.alpha_composite(header_img, (20, 25))
                return main
            else:
                main.alpha_composite(header_img, (20, 25))
                y = 188
                for floor_img in rendered_floors:
                    if floor_img:
                        # floor_bg and floor_bg3 are both 780px wide; main_bg is 820px → 20px side margin
                        main.alpha_composite(floor_img, (20, y))
                        y += floor_img.height + 23
                return main
        except Exception as e:
            raise MOCDataError(f"Error rendering MOC data: {e}")