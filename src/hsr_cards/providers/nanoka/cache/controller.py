"""Versioned cache ownership and initialization orchestration."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ..constants import (
    DEFAULT_ASSET_BASE_URL,
    DEFAULT_BASE_URL,
    DEFAULT_CONCURRENCY,
    DEFAULT_LIVE_VERSION,
    DEFAULT_MANIFEST_URL,
    DEFAULT_STATIC_VERSION,
)
from ..exceptions import NanokaCacheError
from ..http import AsyncHTTP
from ..locales import Locale
from ..models import CacheManifest


from .io import MANIFEST_NAME, default_cache_root, shutil_rmtree
from .manifests import ManifestsMixin
from .json_store import JsonStoreMixin
from .assets import AssetsMixin


class NanokaCache(ManifestsMixin, JsonStoreMixin, AssetsMixin):
    """Versioned, locale-aware JSON and asset cache for static.nanoka.cc."""

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        version: str | None = None,
        locale: Locale | str = Locale.EN,
        base_url: str = DEFAULT_BASE_URL,
        asset_base_url: str = DEFAULT_ASSET_BASE_URL,
        manifest_url: str = DEFAULT_MANIFEST_URL,
        http: AsyncHTTP | None = None,
        include_assets: bool = True,
        concurrency: int = DEFAULT_CONCURRENCY,
        auto_update: bool = False,
    ):
        """Configure version/locale storage and an optional caller-owned HTTP transport.

        cache_dir defaults to .nanoka_cache under the caller working directory.
        version pins a build; None permits later discovery of the newest published
        build. locale accepts Locale aliases. CDN/manifest URLs control downloads,
        include_assets controls bulk asset loading, auto_update revalidates on access,
        and concurrency is clamped to at least one. Construction creates no cache
        files or HTTP session. Injected http remains open when this cache closes;
        invalid locale aliases raise ValueError.
        """
        self.root = Path(cache_dir or default_cache_root()).expanduser().resolve()
        self._pinned_version = bool(version)
        self.version = version or DEFAULT_STATIC_VERSION
        self.live_version = DEFAULT_LIVE_VERSION
        self.locale = Locale.normalize(locale)
        self.base_url = base_url.rstrip("/")
        self.asset_base_url = asset_base_url.rstrip("/")
        self.manifest_url = manifest_url
        self._owns_http = http is None
        self.http = http or AsyncHTTP(concurrency=concurrency)
        self.include_assets = include_assets
        self.concurrency = max(1, concurrency)
        self.auto_update = auto_update
        self._lock = asyncio.Lock()
        self._manifest: CacheManifest | None = None
        self._manifest_dirty = False
        self._write_lock = asyncio.Lock()
        self._validators: dict[str, dict[str, str]] = {}

    @property
    def version_dir(self) -> Path:
        """Return the active build directory under the configured cache root."""
        return self.root / self.version

    @property
    def locale_dir(self) -> Path:
        """Return the active build/locale directory without creating it."""
        return self.version_dir / self.locale.folder

    @property
    def data_dir(self) -> Path:
        """Return the active locale JSON directory without creating it."""
        return self.locale_dir / "data"

    @property
    def assets_dir(self) -> Path:
        """Return the active locale asset directory without creating it."""
        return self.locale_dir / "assets"

    @property
    def manifest_path(self) -> Path:
        """Return the active locale cache manifest path without creating it."""
        return self.locale_dir / MANIFEST_NAME

    async def __aenter__(self) -> "NanokaCache":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the cache-owned HTTP transport; an injected transport remains open."""
        if self._owns_http:
            await self.http.close()

    def exists(self) -> bool:
        """Return whether an active version/locale manifest file exists on disk."""
        return self.manifest_path.is_file()

    async def ensure(self, *, force: bool = False, update: bool = False) -> CacheManifest:
        """Ensure a complete version/locale cache and return its CacheManifest.

        force/update/auto_update revalidate data; otherwise complete cached files are
        reused. Unpinned versions resolve from the global manifest. include_assets
        controls bulk downloads. Concurrent initialization is serialized; network,
        validation, and NanokaCacheError failures propagate.
        """
        async with self._lock:
            manifest = self.read_manifest()
            if not force and not update and not self.auto_update:
                if manifest and manifest.complete:
                    if not self.include_assets or manifest.assets_complete:
                        return manifest
                    return await self._download_assets(manifest)
                # A pinned version without a cache still bootstraps from the
                # CDN; otherwise ``NanokaClient(version="4.6")`` could never
                # download that build's JSON on a first run.
            await self.resolve_version()
            manifest = self.read_manifest()
            if force or update or self.auto_update:
                manifest = manifest or self._new_manifest()
                self._manifest = manifest
                return await self._refresh(manifest)
            if manifest and manifest.complete:
                if not self.include_assets or manifest.assets_complete:
                    return manifest
                return await self._download_assets(manifest)
            manifest = manifest or self._new_manifest()
            self._manifest = manifest
            await self._download_data(manifest)
            if self.include_assets:
                manifest = await self._download_assets(manifest)
            return manifest

    async def update(self, *, force: bool = False) -> CacheManifest:
        """Revalidate catalogs and optional assets and return the active CacheManifest.

        force=True replaces cached data; network/cache failures propagate. Version
        resolution and download ownership follow ensure().
        """
        return await self.ensure(force=force, update=True)

    async def load_json(self, relative_path: str, *, required: bool = True) -> Any | None:
        """Read a cache-relative JSON document after asynchronously ensuring the cache.

        Return None for an absent optional file. required=True or malformed JSON
        raises NanokaCacheError; initialization may download and write cache files.
        """
        await self.ensure()
        path = self.data_dir / relative_path
        if not path.is_file():
            if required:
                raise NanokaCacheError(f"Cached file is missing: {relative_path}")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise NanokaCacheError(f"Could not read cached JSON {relative_path}: {exc}") from exc

    def path_for(self, relative_path: str) -> Path:
        """Return a data-relative path under the active version/locale JSON directory."""
        return self.data_dir / relative_path

    def asset_file(self, relative_path: str) -> Path:
        """Return an asset-relative path under the active version/locale asset directory."""
        return self.assets_dir / relative_path

    async def clear(self) -> None:
        """Remove only this version/locale directory, never the whole cache root."""
        self._manifest = None
        self._validators = {}
        await asyncio.to_thread(shutil_rmtree, self.locale_dir)
        if self.version_dir.is_dir():
            try:
                next(self.version_dir.iterdir())
            except StopIteration:
                await asyncio.to_thread(shutil_rmtree, self.version_dir)
