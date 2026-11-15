"""HoYoLAB player queries independent of card rendering and other providers."""

from __future__ import annotations

from typing import Any

from ..providers.hoyolab.api import BaseAPI, Schedule, Server
from ..providers.hoyolab.models import (
    CalendarData, CalendarResponse, Cookies, CurrencyWarData, CurrencyWarResponse,
    NotesData, NotesResponse,
)
from ..utils.errors import HSR_Error


class HoYoLABClient:
    """Resolve player records through a lazily created or borrowed HoYoLAB API."""

    def __init__(self, uid: int | str, cookie: Cookies | None = None,
                 proxy: str | None = None, *, api: BaseAPI | None = None):
        """Store player configuration; an injected API remains owned by its caller."""
        self.uid = str(uid)
        self.cookie = cookie
        self.proxy = proxy
        self._api = api
        self._owns_api = api is None

    @property
    def api(self) -> BaseAPI:
        """Return the configured API, constructing an IO-free default when needed."""
        if self._api is None:
            self._api = BaseAPI(self.uid, self.cookie.model_dump() if self.cookie else None, self.proxy)
        return self._api

    @property
    def server(self) -> Server:
        """Infer the supported HoYoLAB server from the UID, raising ValueError if invalid."""
        if self.uid.startswith(("1", "8")):
            return "prod_official_asia"
        if self.uid.startswith("6"):
            return "prod_official_usa"
        if self.uid.startswith("7"):
            return "prod_official_eur"
        if self.uid.startswith("5"):
            raise ValueError("HK,TW server is not supported yet.")
        raise ValueError("Invalid UID")

    async def __aenter__(self) -> "HoYoLABClient":
        """Open this client's own API session; borrowed APIs retain their lifecycle."""
        if self._owns_api:
            await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Release internally created API resources."""
        await self.close()

    async def close(self) -> None:
        """Close the owned API only, without constructing a previously unused API."""
        if self._owns_api and self._api is not None:
            await self._api.close()

    async def get_anomaly(self) -> dict[str, Any]:
        """Fetch the player's AA response without creating a card."""
        return await self.api.fetch_anomaly(server=self.server)

    async def get_moc(self, schedule_type: Schedule = "1") -> dict[str, Any]:
        """Fetch all player floors for the current (1) or previous (2) MOC cycle."""
        return await self.api.fetch_moc(schedule_type, server=self.server, need_all="true")

    async def get_pf(self, schedule_type: Schedule = "1") -> dict[str, Any]:
        """Fetch all player floors for the current (1) or previous (2) PF cycle."""
        return await self.api.fetch_pf(schedule_type, server=self.server, need_all="true")

    async def get_shadow(self, schedule_type: Schedule = "1") -> dict[str, Any]:
        """Fetch all player floors for the current (1) or previous (2) AS cycle."""
        return await self.api.fetch_as(schedule_type, server=self.server, need_all="true")

    @staticmethod
    def _validated(response, label: str):
        if response.retcode != 0 or response.data is None:
            raise HSR_Error(f"API error {response.retcode}: {response.message}")
        return response.data

    async def get_calendar(self) -> CalendarData:
        """Return a validated calendar; API failures raise HSR_Error and malformed JSON raises ValidationError."""
        raw = await self.api.fetch_calendar(server=self.server)
        return self._validated(CalendarResponse.model_validate(raw), "calendar")

    async def get_notes(self) -> NotesData:
        """Return validated authenticated daily notes; explicit cookies are required.

        Missing cookies or a nonzero API return code raises HSR_Error. Invalid
        response schemas raise pydantic.ValidationError.
        """
        if self.cookie is None:
            raise HSR_Error("notes() requires user cookies; pass a Cookies object when creating HonkaiStarrail.")
        raw = await self.api.fetch_notes(server=self.server)
        return self._validated(NotesResponse.model_validate(raw), "notes")

    async def get_currency_war(self) -> CurrencyWarData:
        """Return validated recent Currency Wars runs, raising HSR_Error for API errors."""
        raw = await self.api.fetch_currency_war(server=self.server)
        return self._validated(CurrencyWarResponse.model_validate(raw), "currency war")

    async def verify_cookies(self) -> bool:
        """Check explicit cookies through daily notes; absent cookies or request errors return False."""
        if self.cookie is None:
            return False
        try:
            raw = await self.api.fetch_notes(server=self.server)
            return raw.get("retcode", -1) == 0
        except Exception:
            return False


__all__ = ["HoYoLABClient"]
