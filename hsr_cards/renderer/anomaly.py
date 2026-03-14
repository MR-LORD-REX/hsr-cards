from .team import render_team
from .stars import render_stars
from ..utils.hsrfonts import HSRFonts
from ..utils.errors import AnomalyDataError
import asyncio
from PIL import Image , ImageDraw
from io import BytesIO
from pathlib import Path
import aiohttp

main_bg=Path(__file__).parent.parent / "assets"/"backgrounds"/"ANO"/"main_bg.png"

star_boss=Path(__file__).parent.parent / "assets"/"backgrounds"/"ANO"/"star_boss.png"
star_gold=Path(__file__).parent.parent / "assets"/"backgrounds"/"ANO"/"star_gold.png"

class AnomalyRenderer:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.main_bg = Image.open(main_bg).convert("RGBA")
        self.star_boss_img = Image.open(star_boss).convert("RGBA").resize((32, 32))
        self.star_gold_img = Image.open(star_gold).convert("RGBA").resize((32, 32))
    
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

    async def render_mobs(self, mobs: list[dict]):
        offset_y = 213
        f = HSRFonts.get_font(14, "bold")

        for i, mob in enumerate(mobs):
            draw = ImageDraw.Draw(self.main_bg)

            icon = await self.get_icon(mob["monster_icon"])
            icon = icon.resize((90, 90))

            name = mob["monster_name"] or "???"

            self.main_bg.alpha_composite(icon, (1000, 422 + offset_y * i))
            draw.text(
                (1095, 527 + offset_y * i),
                name,
                font=f,
                fill=(255, 255, 255),
                anchor="rm",
            )

        return self.main_bg

    async def render_boss(self, boss: dict, boss_record: dict):
        f = HSRFonts.get_font(20, "bold")
        draw = ImageDraw.Draw(self.main_bg)

        name = boss["name_mi18n"] or "???"
        draw.text((1150, 272), name, font=f, fill=(255, 255, 255), anchor="rt")

        icon = await self.get_icon(boss["icon"])
        icon = icon.resize((125, 170))
        self.main_bg.alpha_composite(icon, (1028, 71))

        tasks = []

        if boss_record["has_challenge_record"]:
            cycles = boss_record["round_num"]
            draw.text((830, 36), str(cycles), font=f, fill=(255, 255, 255))

            stars = boss_record["star_num"]
            buff_text = f"{boss_record['buff']['name_mi18n']}"
            draw.text((500, 247), buff_text, font=f, fill=(255, 255, 255))

            tasks.append(render_team(boss_record["avatars"]))
            tasks.append(render_stars(stars))
            tasks.append(self.get_icon(boss_record["buff"]["icon"]))

            team, stars, buff_icon = await asyncio.gather(*tasks)

            team = team.resize((495, 131))
            buff = buff_icon.resize((60, 60))

            self.main_bg.alpha_composite(team, (498, 91))
            self.main_bg.alpha_composite(buff, (428, 227))
            self.main_bg.alpha_composite(stars, (950, 32))

    async def render_teams_and_mobs(self, mobs: list[dict], teams: list[dict]):
        fb = HSRFonts.get_font(20, "bold")

        await self.render_mobs(mobs)

        draw = ImageDraw.Draw(self.main_bg)

        t_tasks = []
        s_tasks = []
        offset_y = 213

        valid_teams = []

        for team in teams:
            if not team["has_challenge_record"]:
                continue

            valid_teams.append(team)
            t_tasks.append(render_team(team["avatars"]))
            s_tasks.append(render_stars(team["star_num"]))

        teams_imgs = await asyncio.gather(*t_tasks)
        star_imgs = await asyncio.gather(*s_tasks)

        for i in range(len(valid_teams)):
            team_img = teams_imgs[i].resize((431, 114))
            star_img = star_imgs[i]

            t = valid_teams[i]["challenge_time"]
            time_text = f"{t['year']}/{t['month']:02d}/{t['day']:02d} {t['hour']:02d}:{t['minute']:02d}"

            draw.text(
                (830, 365 + offset_y * i),
                f"{valid_teams[i]['round_num']}",
                font=fb,
                fill=(255, 255, 255),
            )

            draw.text(
                (264, 369 + offset_y * i),
                time_text,
                font=fb,
                fill=(255, 255, 255),
            )

            self.main_bg.alpha_composite(team_img, (85, 422 + offset_y * i))
            self.main_bg.alpha_composite(star_img, (938, 361 + offset_y * i))


    async def render_header(self, group: dict, challenge_peak_best_record_brief: dict):
        f = HSRFonts.get_font(24, "bold")
        f16 = HSRFonts.get_font(16, "bold")

        draw = ImageDraw.Draw(self.main_bg)

        total_battle = challenge_peak_best_record_brief["total_battle_num"]
        m_stars = challenge_peak_best_record_brief["mob_stars"]
        b_stars = challenge_peak_best_record_brief["boss_stars"]

        begin = group["begin_time"]
        begin = f"{begin['year']}/{begin['month']:02d}/{begin['day']:02d} {begin['hour']:02d}:{begin['minute']:02d}"

        end = group["end_time"]
        end = f"{end['year']}/{end['month']:02d}/{end['day']:02d} {end['hour']:02d}:{end['minute']:02d}"

        draw.text((70, 240), begin, font=f16, fill=(255, 255, 255))
        draw.text((249, 240), end, font=f16, fill=(255, 255, 255))
        
        if b_stars :
            draw= ImageDraw.Draw(self.main_bg)
            self.main_bg.alpha_composite(self.star_boss_img, (167,111))
            draw.text((197,111),f"x{b_stars}",font=f,fill=(255,255,255))
            
        if m_stars :
            draw= ImageDraw.Draw(self.main_bg)
            self.main_bg.alpha_composite(self.star_gold_img, (282,111))
            draw.text((314,111),f"x{m_stars}",font=f,fill=(255,255,255))
            

        if challenge_peak_best_record_brief["challenge_peak_rank_icon"]:
            icon = await self.get_icon(
                challenge_peak_best_record_brief["challenge_peak_rank_icon"]
            )
            icon = icon.resize((82, 82))
            self.main_bg.alpha_composite(icon, (85, 86))
            
    async def render_anomaly(self, anomaly_data: dict):
        if not anomaly_data['retcode'] == 0 :
            await self.session.close()
            raise AnomalyDataError(f"API returned error code: {anomaly_data['retcode']}",code=anomaly_data['retcode'])
        anomaly_data=anomaly_data['data']
        
        group=anomaly_data['challenge_peak_records'][0]['group']
        brief=anomaly_data["challenge_peak_best_record_brief"]
        boss_info=anomaly_data['challenge_peak_records'][0]['boss_info']
        mob_infos=anomaly_data['challenge_peak_records'][0]['mob_infos']
        
        boss_record=anomaly_data['challenge_peak_records'][0]['boss_record']
        mob_records=anomaly_data['challenge_peak_records'][0]['mob_records']
        
        tasks=[
            self.render_header(group,brief),
            self.render_boss(boss_info,boss_record),
            self.render_teams_and_mobs(mob_infos,mob_records)
        ]
        await asyncio.gather(*tasks)
        await self.session.close()
        return self.main_bg