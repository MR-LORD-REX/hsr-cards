from typing import Literal, Mapping, Optional
from .endpoints import BaseEndpoint, get_default_uid
import aiohttp 
from ..utils.errors import APIError


class BaseAPI:
    def __init__(self, uid: int | str, cookie: Optional[Mapping[str, str]] = None):
        self.uid = uid
        self.cookie=cookie
        self.endpoints = BaseEndpoint(cookie=cookie)
        self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.session:
            await self.session.close()

    async def _fetch_anomaly(self,
        schedule_type: Literal["1"] = "1",
        server: Literal["prod_official_asia", "prod_official_usa", "prod_official_eur", "prod_official_cn", "prod_official_sea"] = "prod_official_asia",
        need_all: Literal["true", "false"] = "false") -> dict:
        params={
            "schedule_type": schedule_type,
            "server": server,
            "role_id": self.uid,
            "need_all": need_all
        }
        headers = self.endpoints.headers
        base_url = self.endpoints.ANOMALY
        try:
            async with self.session.get(base_url, params=params, headers=headers) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching anomaly data: {e}")
            return {}
    
    async def _fetch_moc(self,
        schedule_type: Literal["1", "2"] = "1",
        server: Literal["prod_official_asia", "prod_official_usa", "prod_official_eu", "prod_official_cn", "prod_official_sea"] = "prod_official_asia",
        need_all: Literal["true", "false"] = "false") -> dict:
        params={
            "schedule_type": schedule_type,
            "server": server,
            "role_id": self.uid,
            "need_all": need_all
        }
        headers = self.endpoints.headers
        base_url = self.endpoints.MOC
        try:
            async with self.session.get(base_url, params=params, headers=headers) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching MOC data: {e}")
            return {}
    
    async def _fetch_pf(self,
        schedule_type: Literal["1", "2"] = "1",
        server: Literal["prod_official_asia", "prod_official_usa", "prod_official_eu", "prod_official_cn", "prod_official_sea"] = "prod_official_asia",
        need_all: Literal["true", "false"] = "false") -> dict:
        params={
            "schedule_type": schedule_type,
            "server": server,
            "role_id": self.uid,
            "need_all": need_all
        }
        headers = self.endpoints.headers
        base_url = self.endpoints.PF
        try:
            async with self.session.get(base_url, params=params, headers=headers) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching PF data: {e}")
            return {}
        
    async def _fetch_as(self,
        schedule_type: Literal["1", "2"] = "1",
        server: Literal["prod_official_asia", "prod_official_usa", "prod_official_eu", "prod_official_cn", "prod_official_sea"] = "prod_official_asia",
        need_all: Literal["true", "false"] = "false") -> dict:
        params={
            "schedule_type": schedule_type,
            "server": server,
            "role_id": self.uid,
            "need_all": need_all
        }
        headers = self.endpoints.headers
        base_url = self.endpoints.AS
        try:
            async with self.session.get(base_url, params=params, headers=headers) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching AS data: {e}")
            return {}
    
    async def _fetch_notes(
        self,
        server: Literal[
            "prod_official_asia",
            "prod_official_usa",
            "prod_official_eu",
            "prod_official_cn",
            "prod_official_sea",
        ] = "prod_official_asia",
    ) -> dict:
        params = {"server": server, "role_id": self.uid}
        headers = self.endpoints.headers
        base_url = self.endpoints.NOTES
        try:
            async with self.session.get(base_url, params=params, headers=headers) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching notes data: {e}")
            return {}


    async def _fetch_calendar(
        self,
        server: Literal[
            "prod_official_asia",
            "prod_official_usa",
            "prod_official_eu",
            "prod_official_cn",
            "prod_official_sea",
        ] = "prod_official_asia",
    ) -> dict:
        role_id = self.uid if self.cookie else get_default_uid()
        params = {
            "server": server,
            "role_id": role_id,
        }
        headers = self.endpoints.headers
        base_url = self.endpoints.ACT_CALENDAR
        try:
            async with self.session.get(base_url, params=params, headers=headers) as response:
                return await response.json()
        except Exception as e:
            print(f"Error fetching calendar data: {e}")
            return {}

