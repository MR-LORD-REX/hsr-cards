"""Optional-player convenience facade with independent provider lifecycles."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

import aiohttp
from PIL import Image

from .hoyolab import HoYoLABClient
from .nanoka_cards import NanokaCardMethods
from .player_cards import PlayerCardMethods
from ..builds import BUILD_METADATA_URL, update_build_assets
from ..providers.hoyolab.api import BaseAPI
from ..providers.hoyolab.models import Cookies
from ..renderer.prydwen import TierListRenderer
from ..utils.errors import HSR_Error

# Class imports resolve public injection annotations; resource construction remains lazy.
from .nanoka import NanokaClient
from .prydwen import PrydwenClient
from ..providers.prydwen.models import RedeemCode, TierListData

async def fetch_tier_list(*args, **kwargs) -> TierListData:
    """Forward the legacy patchable fetch entry point to Prydwen's provider API."""
    from ..prydwen.tier_list import fetch_tier_list as fetch
    return await fetch(*args, **kwargs)


class HonkaiStarrail(PlayerCardMethods, NanokaCardMethods):
    """Render cards through independent HoYoLAB, Nanoka, and Prydwen clients.

    A UID is required only for player operations. Provider clients are created
    on first use. Injected clients remain caller-owned; close() and the async
    context release only clients constructed by this facade. Construction and
    context entry perform no requests or credential/file lookups.
    """

    def __init__(
        self, uid: int | str | None = None,
        cookie: Cookies | None = None, proxy: str | None = None, *,
        hoyolab_client: HoYoLABClient | None = None,
        nanoka_client: NanokaClient | None = None,
        prydwen_client: PrydwenClient | None = None,
    ):
        """Store optional player settings and independently borrowed provider clients.

        Existing positional uid/cookie/proxy arguments retain their meaning.
        Omitting UID supports catalog, build, tier, and non-player card methods.
        No network session is opened until an operation needs one.
        """
        self.uid = str(uid) if uid is not None else getattr(hoyolab_client, "uid", None)
        self.cookie = cookie if cookie is not None else getattr(hoyolab_client, "cookie", None)
        self.proxy = proxy
        self._hoyolab = hoyolab_client
        self._nanoka = nanoka_client
        self._prydwen = prydwen_client
        self._owns_hoyolab = hoyolab_client is None
        self._owns_nanoka = nanoka_client is None
        self._owns_prydwen = prydwen_client is None
        self._api_override = None

    @property
    def hoyolab(self) -> HoYoLABClient:
        """Return the player query client; missing UID raises ValueError before IO."""
        if getattr(self, "_hoyolab", None) is None:
            uid = getattr(self, "uid", None)
            if uid is None:
                raise ValueError("A UID is required for HoYoLAB player operations.")
            self._hoyolab = HoYoLABClient(
                uid, getattr(self, "cookie", None), getattr(self, "proxy", None),
                api=getattr(self, "_api_override", None),
            )
            self._owns_hoyolab = True
        return self._hoyolab

    @property
    def nanoka(self) -> NanokaClient:
        """Return the lazy Nanoka domain client with its standard asset-cache settings."""
        if getattr(self, "_nanoka", None) is None:
            from .nanoka import NanokaClient
            self._nanoka = NanokaClient(proxy=getattr(self, "proxy", None))
            self._owns_nanoka = True
        return self._nanoka

    @property
    def prydwen(self) -> PrydwenClient:
        """Return the lazy Prydwen client; it never constructs a HoYoLAB API."""
        if getattr(self, "_prydwen", None) is None:
            from .prydwen import PrydwenClient
            self._prydwen = PrydwenClient(proxy=getattr(self, "proxy", None))
            self._owns_prydwen = True
        return self._prydwen

    @property
    def api(self) -> BaseAPI:
        """Expose the HoYoLAB API for legacy integrations; accessing it requires UID."""
        override = getattr(self, "_api_override", None)
        return override if override is not None else self.hoyolab.api

    @api.setter
    def api(self, value: BaseAPI) -> None:
        """Install a borrowed HoYoLAB API without opening it or transferring ownership.

        Replacing an internally owned API with an open session raises RuntimeError;
        close that API first so replacing it cannot leak its session.
        """
        client = getattr(self, "_hoyolab", None)
        if client is not None:
            old_api = client._api
            if client._owns_api and old_api is not None and getattr(old_api, "_session", None) is not None:
                raise RuntimeError("Close the owned HoYoLAB API before replacing it.")
            client._api = value
            client._owns_api = False
        self._api_override = value

    def _check_server(self):
        """Retain the legacy server lookup through the HoYoLAB query client."""
        return self.hoyolab.server

    async def __aenter__(self) -> HonkaiStarrail:
        """Enter the facade without constructing clients or opening sessions."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Close all internally created provider clients, including on exceptions."""
        await self.close()

    async def close(self) -> None:
        """Release owned clients only; unused and caller-supplied clients stay untouched.

        All owned clients are given a chance to close if one cleanup fails. The
        first failure is re-raised after cleanup; repeated successful calls are safe.
        """
        closers = []
        for name in ("hoyolab", "nanoka", "prydwen"):
            client = getattr(self, "_" + name, None)
            if client is not None and getattr(self, "_owns_" + name, False):
                closers.append(client.close())
        results = await asyncio.gather(*closers, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result

    async def redeem_codes(self) -> list[RedeemCode]:
        """Fetch active HSR redeem codes and rewards through the Prydwen client.

        Makes a public HTTP request without player credentials. Failures are
        wrapped in HSR_Error; an empty provider list remains an empty list.
        """
        try:
            return await self.prydwen.get_redeem_codes()
        except Exception as exc:
            raise HSR_Error(f"Failed to fetch redeem codes: {exc}") from exc

    async def tier_list(
        self, game_mode: Literal["MOC", "PF", "AS"] = "MOC", raw: bool = False, *,
        timeout: float = 30.0,
    ) -> Image.Image | tuple[Image.Image, TierListData]:
        """Render a Prydwen MOC/PF/AS tier list, optionally with its parsed data.

        The default is MOC. timeout controls public HTTP/image requests and this
        facade's proxy applies to Prydwen. This call needs no player UID/cookies;
        provider/render errors raise HSR_Error. The renderer owns its session.
        """
        try:
            # Externally installed legacy APIs can still supply a borrowed image
            # session; normal facade calls remain independent of HoYoLAB.
            legacy_api = getattr(self, "_api_override", None)
            if legacy_api is not None and not hasattr(self, "_owns_prydwen"):
                data = await fetch_tier_list(game_mode=game_mode, timeout=timeout, proxy=self.proxy)
                session = legacy_api.session
            else:
                data = await self.prydwen.get_tier_list(game_mode=game_mode, timeout=timeout, proxy=self.proxy)
                session = None
            async with TierListRenderer(session=session, proxy=self.proxy, timeout=timeout) as renderer:
                image = await renderer.render_tier_list(data)
            return (image, data) if raw else image
        except HSR_Error:
            raise
        except Exception as exc:
            raise HSR_Error(f"Failed to render tier list: {exc}") from exc

    async def update_nanoka_assets(self, *, version: str | None = None, force: bool = False) -> None:
        """Refresh Nanoka data/assets, optionally selecting a published build.

        force revalidates the active cache. Invalid versions and provider/cache
        failures propagate. Injected Nanoka clients retain their settings/lifecycle.
        """
        await self.nanoka.update_assets(version=version, force=force)

    async def character_build(
        self, identifier: int | str | None = None, url: bool = False, *,
        detailed: bool = False, name: str | None = None, element: str | None = None,
        path: str | None = None, rarity: int | None = None, released: bool | None = None,
        include_beta: bool = True, search: str | None = None,
        build_dir: str | Path | None = None, **filters: Any,
    ) -> Image.Image | str | list[Image.Image] | list[str] | None:
        """Return a clean build image/link or detailed summary plus condition pages.

        Identifiers/filters follow Nanoka's catalog rules. Missing variants return
        None. build_dir overrides local build assets; provider errors propagate.
        An existing Nanoka client stays caller/facade-owned; otherwise a temporary
        client loads catalogs without bulk assets and is closed on completion.
        """
        nanoka = getattr(self, "_nanoka", None)
        owns_client = nanoka is None
        if owns_client:
            from .nanoka import NanokaClient
            nanoka = NanokaClient(proxy=getattr(self, "proxy", None), include_assets=False)
        try:
            return await nanoka.character_build(
                identifier, name=name, element=element, path=path, rarity=rarity,
                released=released, include_beta=include_beta, search=search, url=url,
                detailed=detailed, build_dir=build_dir, **filters,
            )
        finally:
            if owns_client:
                await nanoka.close()

    async def update_builds(
        self, *, metadata_url: str = BUILD_METADATA_URL,
        build_dir: str | Path | None = None,
    ) -> int:
        """Download changed community build images; return the updated image count.

        metadata_url selects the manifest and build_dir overrides packaged build
        assets. Own the temporary public-download session; no player UID/cookies
        are required. Invalid metadata or download errors raise HSR_Error.
        """
        async with aiohttp.ClientSession() as session:
            return await update_build_assets(session, metadata_url=metadata_url, build_dir=build_dir)


__all__ = ["HonkaiStarrail"]
