"""Prydwen page requests and explicit build transport factories."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .http import fetch_html
from .models import GameMode, RedeemCode, TierListData, TIER_LIST_URL
from .parsing.codes import PRYDWEN_CODES_URL, parse_redeem_codes
from .parsing.tiers import _normalize_mode, parse_tier_list

if TYPE_CHECKING:
    from .assets import NanokaIndex
    from .fetch import FetchConfig, PrydwenFetcher


class PrydwenAPIClient:
    """Fetch public pages without conflating HTTP and browser build collection.

    Scrapers are scoped to individual blocking requests and run in worker threads.
    Construction does not discover paths, create files, or open a network session.
    Build fetchers have their own async contexts and must be entered by the caller.
    """

    def __init__(self, *, proxy: str | None = None) -> None:
        """Store the default proxy; no network or filesystem side effects occur."""
        self.proxy = proxy

    async def get_html(self, url: str, *, timeout: float = 30.0, proxy: str | None = None) -> str:
        """Return a page body using a seconds timeout and an optional proxy override.

        Raises ValueError for nonpositive timeout and propagates HTTP/dependency
        errors. The request owns and closes its scraper, including on failure.
        """
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        return await asyncio.to_thread(fetch_html, url, timeout, proxy if proxy is not None else self.proxy)

    async def get_redeem_codes(
        self, url: str = PRYDWEN_CODES_URL, *, timeout: float = 30.0,
    ) -> list[RedeemCode]:
        """Return active codes and rewards, or an empty list if the page has none.

        Fetches the page over HTTP; timeout is in seconds. Fetch errors propagate.
        """
        return parse_redeem_codes(await self.get_html(url, timeout=timeout), base_url=url)

    async def get_tier_list(
        self, url: str = TIER_LIST_URL, *, game_mode: GameMode = "MOC",
        timeout: float = 30.0, proxy: str | None = None,
    ) -> TierListData:
        """Return parsed MOC, PF, or AS ranking data from one fetched page.

        Mode aliases are case-insensitive. Raises ValueError before network access
        for unsupported modes/timeouts and after parsing when rankings are absent.
        A per-call proxy overrides the default proxy.
        """
        _normalize_mode(game_mode)
        html = await self.get_html(url, timeout=timeout, proxy=proxy)
        return parse_tier_list(html, game_mode=game_mode, source=url)

    def build_fetcher(self, config: FetchConfig, *, nanoka: NanokaIndex | None = None) -> PrydwenFetcher:
        """Create a cache-first build fetcher using config's HTTP/browser transport.

        The caller enters its async context and owns closure. Browser imports and
        launches occur only for explicit browser transport when that context opens.
        """
        from .fetch import PrydwenFetcher
        return PrydwenFetcher(config, nanoka=nanoka)

    async def close(self) -> None:
        """Finish client ownership; each request already closes its scoped scraper."""

    async def __aenter__(self) -> "PrydwenAPIClient":
        """Return this API client without eagerly opening a request session."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close this API client after the enclosing async operation completes."""
        await self.close()