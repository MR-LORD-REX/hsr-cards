"""Player-card methods delegated through the HoYoLAB query client."""
from __future__ import annotations

from typing import Literal
from PIL import Image

from ..renderer.hoyolab import (AnomalyRenderer, MOCRenderer, PFRenderer, ASRenderer,
    BannerRenderer, EventsRenderer, EndgameRenderer, NotesRenderer, CurrencyWarRenderer)
from ..renderer.hoyolab.currencywar import CurrencyWarResult
from ..providers.hoyolab.models import CalendarData, NotesData, CurrencyWarData
from ..utils.errors import HSR_Error


class PlayerCardMethods:
    """Render HoYoLAB responses through the facade's independent player client.

    Each async card method requests player/calendar data and may download image
    assets. A supported UID is required; authenticated notes require explicit
    cookies. Renderers own temporary image sessions, while the facade owns only
    the query clients it constructs. Card failures are wrapped in HSR_Error.
    """

    async def anomaly(self)-> Image.Image:
        """Render the player AA record; API or rendering errors raise HSR_Error."""
        try:
            data = await self.hoyolab.get_anomaly()
            async with AnomalyRenderer() as renderer:
                img=await renderer.render_anomaly(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render anomaly: {e}")

    async def MOC(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        """Render current (1) or previous (2) player MOC floors as a PIL image."""
        try:
            data = await self.hoyolab.get_moc(schedule_type)
            async with MOCRenderer() as renderer:
                img=await renderer.render_moc(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render MOC: {e}")

    async def PF(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        """Render current (1) or previous (2) player PF floors as a PIL image."""
        try:
            data = await self.hoyolab.get_pf(schedule_type)
            async with PFRenderer() as renderer:
                img=await renderer.render_pf(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render PF: {e}")

    async def shadow(self,
        schedule_type: Literal["1", "2"] = "1",
        )-> Image.Image:
        """Render current (1) or previous (2) player AS floors as a PIL image."""
        try:
            data = await self.hoyolab.get_shadow(schedule_type)
            async with ASRenderer() as renderer:
                img=await renderer.render_AS(data)
                return img
        except Exception as e:
            raise HSR_Error(f"Failed to render shadow: {e}")

    async def _calendar(self) -> CalendarData:
        """Fetch the validated player/public calendar using the HoYoLAB client."""
        try:
            return await self.hoyolab.get_calendar()
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to fetch calendar: {e}")

    async def banners(self) -> Image.Image:
        """Render calendar banners as a PIL image; failures raise HSR_Error."""
        try:
            cal = await self._calendar()
            async with BannerRenderer() as renderer:
                return await renderer.render_banners(cal)
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render banners: {e}")

    async def events(self) -> Image.Image:
        """Render personalized calendar events when explicit cookies are supplied."""
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
        """Render the HoYoLAB schedule calendar as a PIL image."""
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
        """Render authenticated daily notes; raw=True also returns validated NotesData."""
        try:
            data = await self.hoyolab.get_notes()
            async with NotesRenderer() as renderer:
                img = renderer.render_notes(data)
            if raw:
                return img, data
            return img
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render notes: {e}")

    async def currency_war(
        self,
        index: int = 0,
        raw: bool = False,
    ) -> "CurrencyWarResult | tuple[CurrencyWarResult, CurrencyWarData]":
        """Render one Currency Wars run.

        ``index`` follows the API order (0 is the most recent run) and accepts
        negative values. The result exposes ``image``, ``current``, ``next()``,
        ``prev()`` and ``all`` for paging through the recent runs. raw=True
        additionally returns validated CurrencyWarData. API/render errors,
        including an unavailable run index, are wrapped in HSR_Error.
        """
        try:
            data = await self.hoyolab.get_currency_war()
            async with CurrencyWarRenderer() as renderer:
                result = await renderer.render_currency_war(data, index)
            if raw:
                return result, data
            return result
        except HSR_Error:
            raise
        except Exception as e:
            raise HSR_Error(f"Failed to render currency war: {e}")

    async def verify_cookies(self) -> bool:
        """Check explicit HoYoLAB cookies; absent cookies or request errors return False."""
        if getattr(self, "cookie", None) is None:
            return False
        try:
            return await self.hoyolab.verify_cookies()
        except Exception:
            return False
