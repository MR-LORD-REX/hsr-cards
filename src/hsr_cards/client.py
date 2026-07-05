from typing import Literal
from .renderer.anomaly import AnomalyRenderer
from .renderer.moc import MOCRenderer
from .renderer.finction import PFRenderer
from .renderer.shadow import ASRenderer
from .renderer.banners import BannerRenderer
from .renderer.events import EventsRenderer
from .renderer.endgame import EndgameRenderer
from .renderer.notes import NotesRenderer
from .api.base_api import BaseAPI
from .utils.errors import HSR_Error
from .models.auth import Cookies
from .models.events import CalendarData, CalendarResponse
from .models.notes import NotesResponse, NotesData
from PIL import Image

class HonkaiStarrail:
    def __init__(self, uid: int | str, cookie: Cookies | None = None):
        self.uid = str(uid)
        self.cookie = cookie
        cookie_dict = cookie.model_dump() if cookie is not None else None
        self.api = BaseAPI(self.uid, cookie=cookie_dict)
        
    def _check_server(self):
        if self.uid.startswith("1") or self.uid.startswith("8"):
            return 'prod_official_asia'
        elif self.uid.startswith("6"):
            return 'prod_official_usa'
        elif self.uid.startswith("7"):
            return 'prod_official_eur'
        elif self.uid.startswith("5"):
            raise ValueError("HK,TW server is not supported yet.")
        else:
            raise ValueError("Invalid UID")
        
    async def __aenter__(self):
        await self.api.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.api.__aexit__(exc_type, exc_val, exc_tb)
    
    async def anomaly(self)-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_anomaly(server=server)
            async with AnomalyRenderer() as renderer:
                img=await renderer.render_anomaly(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render anomaly: {e}")
        
    async def MOC(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_moc(schedule_type,server=server, need_all="true")
            async with MOCRenderer() as renderer:
                img=await renderer.render_moc(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render MOC: {e}")
    
    async def PF(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_pf(schedule_type,server=server, need_all="true")
            async with PFRenderer() as renderer:
                img=await renderer.render_pf(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render PF: {e}")
        
    async def shadow(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        try:
            server=self._check_server()
            if not server:
                raise ValueError("Invalid UID")
            data= await self.api._fetch_as(schedule_type,server=server, need_all="true")
            async with ASRenderer() as renderer:
                img=await renderer.render_AS(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render shadow: {e}")

    async def _calendar(self) -> CalendarData:
        try:
            server = self._check_server()
            raw = await self.api._fetch_calendar(server=server)
            parsed = CalendarResponse.model_validate(raw)
            if parsed.retcode != 0 or parsed.data is None:
                raise HSR_Error(f"API error {parsed.retcode}: {parsed.message}")
            return parsed.data
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to fetch calendar: {e}")

    async def banners(self) -> Image.Image:
        try:
            cal = await self._calendar()
            async with BannerRenderer() as renderer:
                return await renderer.render_banners(cal)
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render banners: {e}")

    async def events(self) -> Image.Image:
        try:
            cal = await self._calendar()
            personalised = self.cookie is not None
            async with EventsRenderer() as renderer:
                return await renderer.render_events(
                    cal.act_list,
                    personalised=personalised,
                    now_ts=cal.now,
                )
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render events: {e}")

    async def endgame(self) -> Image.Image:
        try:
            cal = await self._calendar()
            personalised = self.cookie is not None
            async with EndgameRenderer() as renderer:
                return await renderer.render_endgame(
                    cal.challenge_list,
                    personalised=personalised,
                    now_ts=cal.now,
                )
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render endgame: {e}")

    async def notes(self, raw: bool = False) -> Image.Image | tuple[Image.Image, NotesData]:
        if self.cookie is None:
            raise HSR_Error("notes() requires user cookies — pass a Cookies object when creating HonkaiStarrail.")
        try:
            server   = self._check_server()
            raw_data = await self.api._fetch_notes(server=server)
            parsed   = NotesResponse.model_validate(raw_data)
            if parsed.retcode != 0 or parsed.data is None:
                raise HSR_Error(f"API error {parsed.retcode}: {parsed.message}")
            async with NotesRenderer() as renderer:
                img = renderer.render_notes(parsed.data)
            if raw:
                return img, parsed.data
            return img
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render notes: {e}")

    async def verify_cookies(self) -> bool:
        if self.cookie is None:
            return False
        try:
            server = self._check_server()
            raw    = await self.api._fetch_notes(server=server)
            return raw.get("retcode", -1) == 0
        except Exception:
            return False
