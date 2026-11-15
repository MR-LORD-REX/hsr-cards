"""HoYoLAB HTTP operations with lazy sessions and explicit ownership."""

from __future__ import annotations

from typing import Any, Literal, Mapping

import aiohttp

from .endpoints import BaseEndpoint, get_default_uid

Server = Literal["prod_official_asia", "prod_official_usa", "prod_official_eur", "prod_official_eu", "prod_official_cn", "prod_official_sea"]
Schedule = Literal["1", "2"]
NeedAll = Literal["true", "false"]


class BaseAPI:
    """Request HoYoLAB data without opening a session during construction.

    ``session`` may be supplied by the caller and remains caller-owned. Otherwise
    a session is created on first use and closed by close()/the async context.
    Credentials and default calendar settings are resolved only for a request.
    """

    def __init__(self, uid: int | str, cookie: Mapping[str, str] | None = None,
                 proxy: str | None = None, *, session: aiohttp.ClientSession | None = None):
        """Store request configuration; no HTTP, credential lookup, or file IO occurs."""
        self.uid = uid
        self.cookie = cookie
        self.proxy = proxy
        self._session = session
        self._owns_session = session is None
        self._endpoints: BaseEndpoint | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Return the borrowed session or lazily create an internally owned session.

        Accessing this property requires a running event loop when construction
        is necessary. A closed borrowed session raises RuntimeError.
        """
        if self._session is None or (self._owns_session and self._session.closed):
            self._session = aiohttp.ClientSession()
        if self._session.closed:
            raise RuntimeError("The supplied HoYoLAB session is closed")
        return self._session

    @session.setter
    def session(self, value: aiohttp.ClientSession) -> None:
        """Install a caller-owned session without abandoning an open owned session.

        Assigning the existing session preserves ownership. Replacing an open
        internally created session raises RuntimeError; close it first. Borrowed
        sessions are never closed when replaced or when this API is closed.
        """
        if value is self._session:
            return
        if self._owns_session and self._session is not None and not self._session.closed:
            raise RuntimeError("Close the owned HoYoLAB session before replacing it.")
        self._session = value
        self._owns_session = False

    @property
    def endpoints(self) -> BaseEndpoint:
        """Resolve request headers from explicit cookies or configured environment values."""
        if self._endpoints is None:
            self._endpoints = BaseEndpoint(cookie=self.cookie)
        return self._endpoints

    @endpoints.setter
    def endpoints(self, value: BaseEndpoint) -> None:
        """Replace endpoint configuration, for example for an injected test transport."""
        self._endpoints = value

    async def __aenter__(self) -> "BaseAPI":
        """Open the lazy session without resolving credentials or making a request."""
        self.session
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Close the internally owned session while preserving borrowed sessions."""
        await self.close()

    async def close(self) -> None:
        """Close only the session created by this API; repeated calls are harmless."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Decode one response, retaining the historical empty result on transport errors."""
        endpoints = self.endpoints
        url = getattr(endpoints, endpoint)
        request_options: dict[str, Any] = {"params": params, "headers": endpoints.headers}
        if self.proxy:
            request_options["proxy"] = self.proxy
        try:
            async with self.session.get(url, **request_options) as response:
                return await response.json()
        except (aiohttp.ClientError, OSError, ValueError):
            return {}

    async def _challenge(self, endpoint: str, schedule_type: str, server: Server, need_all: NeedAll) -> dict[str, Any]:
        return await self._request(endpoint, {
            "schedule_type": schedule_type, "server": server,
            "role_id": self.uid, "need_all": need_all,
        })

    async def fetch_anomaly(self, schedule_type: Literal["1"] = "1", server: Server = "prod_official_asia",
                            need_all: NeedAll = "false") -> dict[str, Any]:
        """Fetch AA player records; return raw JSON or an empty dict on transport failure."""
        return await self._challenge("ANOMALY", schedule_type, server, need_all)

    async def fetch_moc(self, schedule_type: Schedule = "1", server: Server = "prod_official_asia",
                        need_all: NeedAll = "false") -> dict[str, Any]:
        """Fetch current (1) or previous (2) Memory of Chaos player records as raw JSON."""
        return await self._challenge("MOC", schedule_type, server, need_all)

    async def fetch_pf(self, schedule_type: Schedule = "1", server: Server = "prod_official_asia",
                       need_all: NeedAll = "false") -> dict[str, Any]:
        """Fetch current (1) or previous (2) Pure Fiction player records as raw JSON."""
        return await self._challenge("PF", schedule_type, server, need_all)

    async def fetch_as(self, schedule_type: Schedule = "1", server: Server = "prod_official_asia",
                       need_all: NeedAll = "false") -> dict[str, Any]:
        """Fetch current (1) or previous (2) Apocalyptic Shadow player records as raw JSON."""
        return await self._challenge("AS", schedule_type, server, need_all)

    async def fetch_currency_war(self, server: Server = "prod_official_asia") -> dict[str, Any]:
        """Fetch recent Currency Wars player runs; transport failures return an empty dict."""
        return await self._request("CURRENCY_WAR", {"server": server, "role_id": self.uid})

    async def fetch_notes(self, server: Server = "prod_official_asia") -> dict[str, Any]:
        """Fetch authenticated daily notes; transport failures return an empty dict."""
        return await self._request("NOTES", {"server": server, "role_id": self.uid})

    async def fetch_calendar(self, server: Server = "prod_official_asia") -> dict[str, Any]:
        """Fetch the personalized or configured public calendar without rendering it.

        Explicit cookies use this API's UID/server. The public mode retains the
        configured default UID and Asia server. Missing configuration raises
        ValueError; network failures return an empty dict.
        """
        role_id = self.uid if self.cookie else get_default_uid()
        return await self._request("ACT_CALENDAR", {
            "server": server if self.cookie else "prod_official_asia", "role_id": role_id,
        })

    # Retain the historical private request names for existing integrations.
    _fetch_anomaly = fetch_anomaly
    _fetch_moc = fetch_moc
    _fetch_pf = fetch_pf
    _fetch_as = fetch_as
    _fetch_currency_war = fetch_currency_war
    _fetch_notes = fetch_notes
    _fetch_calendar = fetch_calendar


HoYoLABAPI = BaseAPI
__all__ = ["BaseAPI", "HoYoLABAPI", "Server", "Schedule", "NeedAll"]
