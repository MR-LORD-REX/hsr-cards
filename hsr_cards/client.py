from typing import Literal
from .renderer.anomaly import AnomalyRenderer
from .renderer.moc import MOCRenderer
from .renderer.finction import PFRenderer
from .renderer.shadow import ASRenderer
from .api.base_api import BaseAPI
from .utils.errors import HSR_Error
from PIL import Image

class HonkaiStarrail:
    def __init__(self, uid:int|str, cookie:dict[str, str]|None=None):
        self.uid = str(uid)
        self.cookie = cookie
        self.api = BaseAPI(self.uid)
        
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