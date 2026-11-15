"""Raw Nanoka catalog, detail, and asset access through a versioned cache."""
from __future__ import annotations

from pathlib import Path
from typing import Any


from .cache import NanokaCache, default_cache_root, mode_key
from .constants import (
    DEFAULT_ASSET_BASE_URL,
    DEFAULT_BASE_URL,
    DEFAULT_CONCURRENCY,
    DEFAULT_STATIC_VERSION,
    MODE_DETAIL_FOLDERS,
)
from .endpoints import DETAIL_FOLDERS
from .exceptions import NanokaAssetError, NanokaNotFoundError
from .http import AsyncHTTP
from .locales import DEFAULT_LOCALE, Locale
from .models import NanokaVersions


class NanokaAPIClient:
    """Fetch raw provider data through a versioned disk cache.

    Created resources are owned; injected cache/HTTP resources remain caller-owned.
    Construction performs no network or filesystem IO.
    """

    def __init__(
        self,
        *,
        version: str | None = None,
        language: Locale | str = DEFAULT_LOCALE,
        cache_dir: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        asset_base_url: str = DEFAULT_ASSET_BASE_URL,
        proxy: str | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        include_assets: bool = True,
        auto_update: bool = False,
        concurrency: int = DEFAULT_CONCURRENCY,
        cache: NanokaCache | None = None,
        http: AsyncHTTP | None = None,
    ):
        """Configure raw data access without downloading files or opening a session.

        version=None resolves the newest build on first initialization; language
        accepts Locale aliases. cache_dir defaults to caller-relative .nanoka_cache.
        HTTP uses the configured bases, proxy, 30-second timeout, three retries,
        and bounded concurrency. include_assets controls bulk asset downloads;
        auto_update revalidates on cache access. Injected cache settings take
        precedence over constructor settings. An injected HTTP/cache remains
        caller-owned; otherwise this client closes the resources it creates.
        Invalid language aliases raise ValueError.
        """
        self.language = Locale.normalize(language)
        self.version = version or DEFAULT_STATIC_VERSION
        self.cache_dir = Path(cache_dir or default_cache_root()).expanduser().resolve()
        self.base_url = base_url.rstrip("/")
        self.asset_base_url = asset_base_url.rstrip("/")
        self.include_assets = include_assets
        self.auto_update = auto_update
        self._owns_cache = cache is None
        self._owns_http = cache is None and http is None
        self._http = (cache.http if cache is not None else http) or AsyncHTTP(
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            concurrency=concurrency,
        )
        self._cache = cache or NanokaCache(
            cache_dir=self.cache_dir,
            version=version,
            locale=self.language,
            base_url=self.base_url,
            asset_base_url=self.asset_base_url,
            http=self._http,
            include_assets=include_assets,
            concurrency=concurrency,
            auto_update=auto_update,
        )

        if cache is not None:
            self.language = cache.locale
            self.version = cache.version
            self.cache_dir = cache.root
            self.base_url = cache.base_url
            self.asset_base_url = cache.asset_base_url
            self.include_assets = cache.include_assets
            self.auto_update = cache.auto_update

    @property
    def cache(self) -> NanokaCache:
        """Return the configured cache; reading this property performs no IO."""
        return self._cache

    @property
    def cache_path(self) -> Path:
        """Return the active version/locale directory without creating it."""
        return self._cache.locale_dir

    async def __aenter__(self) -> "NanokaAPIClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close only cache and HTTP resources created by this API client.

        Injected resources remain caller-owned; await this on the owning event loop.
        """
        if self._owns_cache:
            await self._cache.close()
        if self._owns_http:
            await self._http.close()

    async def initialize(self, *, force: bool = False) -> "NanokaAPIClient":
        """Ensure catalogs and optional assets for the configured version/locale.

        force=True refreshes cached data. Return this client after resolving its version;
        network and NanokaCacheError failures propagate. Construction itself stays offline.
        """
        await self._cache.ensure(force=force)
        self.version = self._cache.version
        return self

    async def get_versions(self, *, refresh: bool = False) -> NanokaVersions:
        """Return the builds currently published by Nanoka.

        ``live_server`` is the stable game build (for example ``4.7``) and
        ``live_beta`` is the newest published patch build (for example
        ``4.7.51``). ``versions`` contains every selectable build.
        refresh=True replaces cached global metadata when the CDN is available;
        otherwise existing complete cache metadata may be used. Network/file
        writes are possible and cache/transport failures propagate.
        """
        return await self._cache.versions(refresh=refresh)

    async def update_assets(
        self,
        *,
        version: str | None = None,
        force: bool = False,
    ) -> "NanokaAPIClient":
        """Revalidate/download one published build, or the active build.

        Passing ``version`` also switches the client to that build, so a
        subsequent card render reads the assets that were just refreshed.
        Unknown published versions raise ValueError before switching. force=True
        replaces cached data; cache/transport failures propagate. Return this
        API client after synchronizing the active version.
        """
        target = str(version).strip() if version else None
        if target:
            published = await self.get_versions()
            if target not in published.versions:
                raise ValueError(
                    f"Unknown Nanoka version {target!r}; choose one of "
                    f"{', '.join(published.versions)}"
                )
            self.version = target
            self._cache.version = target
            self._cache._pinned_version = True
            self._cache._manifest = None
            self._cache._validators = {}
        await self._cache.update(force=force)
        self.version = self._cache.version
        return self

    async def clear_cache(self, *, version: str | None = None) -> None:
        """Remove one cached build, or all version trees/global metadata when omitted.

        Deletion is scoped to the configured cache root; active-build metadata is
        invalidated so later access can initialize it again. This performs file IO.
        """
        await self._cache.clear_version(version)

    async def prepare(self, refresh: bool = False) -> None:
        """Initialize missing data, or revalidate catalogs when refresh=True.

        Synchronize the active version after cache discovery. This may perform network
        requests and write cache files; transport/cache errors propagate.
        """
        if refresh:
            await self._cache.update()
        else:
            await self._cache.ensure()
        self.version = self._cache.version

    async def document(self, relative_path: str, *, required: bool = True) -> Any | None:
        """Read original JSON from a cache-relative path for this version/locale.

        Preserve list/mapping/scalar payloads. Return None for an absent optional
        document; missing required or malformed files raise NanokaCacheError.
        Missing cache data is initialized asynchronously, which may download/write
        files. Synchronize the resolved version; cache/transport failures propagate.
        """
        payload = await self._cache.load_json(relative_path, required=required)
        self.version = self._cache.version
        return payload

    async def catalog(self, filename: str, *, required: bool = True) -> dict[str, Any]:
        """Load a cache-relative catalog document for this version and locale.

        Return a mapping, or {} for an absent optional or non-mapping document.
        required=True raises NanokaCacheError for a missing file. Missing cache data is
        initialized asynchronously and the resolved version is synchronized.
        """
        payload = await self.document(filename, required=required)
        return payload if isinstance(payload, dict) else {}

    async def detail(
        self,
        kind: str,
        identifier: int | str,
        *,
        required: bool = True,
        refresh: bool = False,
    ) -> dict[str, Any] | list[Any] | None:
        """Load an original detail document by canonical kind and numeric ID.

        Return dict/list JSON, or None when absent and required=False; required=True
        raises NanokaNotFoundError. Unknown kinds raise KeyError. refresh=True
        revalidates the version/locale cache; cache and transport failures propagate.
        """
        await self.prepare(refresh)
        folder = MODE_DETAIL_FOLDERS[kind] if kind in MODE_DETAIL_FOLDERS else DETAIL_FOLDERS[kind]
        payload = await self.document(f"{folder}/{identifier}.json", required=False)
        if payload is None:
            if required:
                raise NanokaNotFoundError(kind, identifier)
            return None
        return payload

    async def get_endgame_payload(
        self, identifier: int | str, *, mode: str = "maze", refresh: bool = False
    ) -> dict[str, Any] | list[Any]:
        """Return an unmodified season document for a canonical mode or alias.

        Version and locale belong to this client. Refresh revalidates its cache;
        missing seasons raise NanokaNotFoundError, unknown modes raise ValueError.
        AA data access does not enable AA cards. Dict/list payloads keep all fields.
        """
        return await self.detail(mode_key(mode), identifier, refresh=refresh)

    async def fetch_asset(self, relative: str, *, refresh: bool = False) -> Path | None:
        """Cache a CDN-relative asset and return its path, or None if unavailable.

        Refresh revalidates the build first. Missing/invalid asset responses return
        None; cache initialization and transport errors propagate.
        """
        await self.prepare(refresh)
        normalized = relative.replace("\\", "/").lstrip("/")
        path = self._cache.asset_file(normalized)
        if path.is_file() and not refresh:
            return path
        try:
            return await self._cache.asset(normalized)
        except NanokaAssetError:
            return None


__all__ = ["NanokaAPIClient"]
