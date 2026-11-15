"""Nanoka domain client with independently owned provider API access."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from ..providers.nanoka.api import NanokaAPIClient
from ..providers.nanoka.cache import NanokaCache
from ..providers.nanoka.constants import DEFAULT_ASSET_BASE_URL, DEFAULT_BASE_URL, DEFAULT_CONCURRENCY
from ..providers.nanoka.locales import DEFAULT_LOCALE, Locale
from ..providers.nanoka.models import NanokaVersions
from ..providers.nanoka.results import BossEncounter, EndgameSeason, Character, LightCone, RelicSet, Monster
from ..providers.nanoka.characters import CharactersQueries
from ..providers.nanoka.equipment import EquipmentQueries
from ..providers.nanoka.monsters import MonstersQueries
from ..providers.nanoka.schedules import SchedulesQueries
from ..providers.nanoka.items import ItemsQueries
from ..providers.nanoka.assets import AssetsQueries
from ..providers.nanoka.catalogs import resolve_asset_path

ModeName = Literal["maze", "maze_extra", "maze_boss", "maze_peak"]


class NanokaClient(CharactersQueries, EquipmentQueries, MonstersQueries, SchedulesQueries, ItemsQueries, AssetsQueries):
    """Query domain objects through a versioned, locale-aware Nanoka API client.

    Defaults preserve the caller-relative .nanoka_cache layout. An injected
    api_client keeps its version/locale/settings and remains caller-owned.
    Construction is offline; data methods initialize the cache asynchronously.
    """

    def __init__(
        self, *, version: str | None = None, language: Locale | str = DEFAULT_LOCALE,
        cache_dir: str | Path | None = None, base_url: str = DEFAULT_BASE_URL,
        asset_base_url: str = DEFAULT_ASSET_BASE_URL, proxy: str | None = None,
        timeout: float = 30.0, retries: int = 3, include_assets: bool = True,
        auto_update: bool = False, concurrency: int = DEFAULT_CONCURRENCY,
        api_client: NanokaAPIClient | None = None,
    ):
        """Configure the domain client and optional caller-owned provider API.

        Without api_client, forward version/Locale aliases, caller-relative cache
        root, CDN bases, proxy, timeout/retries, asset refresh settings, and
        concurrency to a new NanokaAPIClient. version=None resolves the newest
        published build on first async query. An injected API keeps its own
        configuration and is never closed here. Invalid language aliases raise
        ValueError. Construction performs no downloads or cache writes.
        """
        self._owns_api_client = api_client is None
        self.api_client = api_client or NanokaAPIClient(
            version=version, language=language, cache_dir=cache_dir, base_url=base_url,
            asset_base_url=asset_base_url, proxy=proxy, timeout=timeout, retries=retries,
            include_assets=include_assets, auto_update=auto_update, concurrency=concurrency,
        )
        self._sync_configuration()

    def _sync_configuration(self) -> None:
        for name in ("language", "version", "cache_dir", "base_url", "asset_base_url", "include_assets", "auto_update"):
            setattr(self, name, getattr(self.api_client, name))

    @property
    def _cache(self) -> NanokaCache:
        return self.api_client.cache

    @property
    def _http(self):
        return self.api_client._http

    @property
    def cache(self) -> NanokaCache:
        """Return the provider cache without initializing or downloading data."""
        return self.api_client.cache

    @property
    def cache_path(self) -> Path:
        """Return the active version/locale directory under the configured cache root."""
        return self.api_client.cache_path

    async def __aenter__(self) -> "NanokaClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close an internally created API client; injected clients remain open."""
        if self._owns_api_client:
            await self.api_client.close()

    async def initialize(self, *, force: bool = False) -> "NanokaClient":
        """Download missing catalogs/assets, optionally replacing the cached build.

        Return this client after synchronizing the resolved version. Network/cache
        errors propagate; an unpinned first call may select a newer published build.
        """
        await self.api_client.initialize(force=force)
        self._sync_configuration()
        return self

    async def get_versions(self, *, refresh: bool = False) -> NanokaVersions:
        """Return published builds and live/beta versions, optionally refreshing metadata."""
        return await self.api_client.get_versions(refresh=refresh)

    async def update_assets(self, *, version: str | None = None, force: bool = False) -> "NanokaClient":
        """Refresh data/assets, switching to a published build when supplied.

        Unknown versions raise ValueError before changing the active build. Cache
        and transport failures propagate; return this client for chained queries.
        """
        await self.api_client.update_assets(version=version, force=force)
        self._sync_configuration()
        return self

    async def clear_cache(self, *, version: str | None = None) -> None:
        """Remove one cached build, or all builds and global metadata when omitted."""
        await self.api_client.clear_cache(version=version)

    async def _prepare(self, refresh: bool = False) -> None:
        await self.api_client.prepare(refresh)
        self._sync_configuration()

    async def _catalog(self, filename: str, *, required: bool = True) -> dict[str, Any]:
        return await self.api_client.catalog(filename, required=required)

    async def _read_json(self, relative_path: str, *, required: bool = True) -> Any | None:
        payload = await self.api_client.document(relative_path, required=required)
        self._sync_configuration()
        return payload

    async def _detail(self, kind: str, identifier: int | str, *, required: bool = True, refresh: bool = False):
        payload = await self.api_client.detail(kind, identifier, required=required, refresh=refresh)
        self._sync_configuration()
        return payload

    async def get_endgame_payload(self, identifier: int | str, *, mode: str = "maze", refresh: bool = False) -> dict[str, Any] | list[Any]:
        """Return a season's original JSON fields using a canonical mode or alias.

        Preserve parameter arrays/descriptions and list-shaped payloads for card
        services. Refresh revalidates the active version and locale cache; missing
        seasons raise NanokaNotFoundError, unknown modes raise ValueError.
        This exposes AA data without enabling AA floor-card rendering.
        """
        payload = await self.api_client.get_endgame_payload(identifier, mode=mode, refresh=refresh)
        self._sync_configuration()
        return payload


__all__ = ["NanokaClient", "ModeName", "Character", "LightCone", "RelicSet", "Monster", "BossEncounter", "EndgameSeason", "resolve_asset_path"]
