"""Catalog/detail downloads, validators, and refresh behavior."""
from __future__ import annotations

import json
from typing import Any, Iterable

from ..endpoints import (
    CATALOG_DETAIL_KINDS,
    DIFF_ENDPOINTS,
    LOCALIZED_ROOT_ENDPOINTS,
    ROOT_ENDPOINTS,
    VERSION_ENDPOINTS,
    Endpoint,
    detail_endpoint,
)
from ..exceptions import NanokaCacheError, NanokaHTTPError
from ..models import CacheManifest


from .io import gather_bounded, atomic_write_bytes


class JsonStoreMixin:
    """Download, revalidate, and discover JSON catalog/detail documents."""

    async def _download_data(self, manifest: CacheManifest) -> None:
        await self._download_endpoints(manifest, ROOT_ENDPOINTS)
        await self._download_endpoints(manifest, LOCALIZED_ROOT_ENDPOINTS)
        await self._download_endpoints(manifest, VERSION_ENDPOINTS)
        specs = self._discover_details(manifest)
        await self._download_details(manifest, specs)
        manifest.complete = True
        await self._write_manifest(manifest, force=True)

    async def _download_endpoints(
        self,
        manifest: CacheManifest,
        endpoints: Iterable[Endpoint],
        *,
        revalidate: bool = False,
    ) -> None:
        pending = list(endpoints)
        for index in range(0, len(pending), self.concurrency):
            batch = pending[index:index + self.concurrency]
            await gather_bounded(
                self._download_endpoint(
                    manifest,
                    endpoint,
                    allow_missing=not endpoint.required,
                    revalidate=revalidate,
                )
                for endpoint in batch
            )
            await self._write_manifest(manifest)

    async def _download_endpoint(
        self,
        manifest: CacheManifest,
        endpoint: Endpoint,
        *,
        allow_missing: bool = False,
        revalidate: bool = False,
    ) -> bool:
        relative = endpoint.key
        destination = self.data_dir / relative
        if destination.is_file() and not revalidate:
            return True
        url = endpoint.url(self.base_url, self.version, self.locale.folder)
        try:
            response = await self.http.get(
                url,
                allow_404=True,
                use_cache=True,
                cache=self,
            )
        except NanokaHTTPError:
            if endpoint.required and not allow_missing:
                raise
            return False
        if response.status == 304:
            self._record_validator(relative, response)
            return True
        if response.status == 404 or not response.body:
            if endpoint.required and not allow_missing:
                raise NanokaCacheError(f"Required Nanoka document returned 404: {url}")
            return False
        atomic_write_bytes(destination, response.body)
        self._record_validator(relative, response)
        if relative not in manifest.root_files:
            manifest.root_files.append(relative)
        self._touch()
        return True

    def _record_validator(self, relative: str, response: Any) -> None:
        validator: dict[str, str] = {}
        if getattr(response, "etag", None):
            validator["etag"] = response.etag
        if getattr(response, "last_modified", None):
            validator["last_modified"] = response.last_modified
        if validator and self._validators.get(relative) != validator:
            self._validators[relative] = validator
            self._touch()

    def _record_validator_for_url(self, url: str, response: Any) -> None:
        relative = self._relative_for_url(url)
        if relative is not None:
            self._record_validator(relative, response)

    async def validator(self, url: str) -> dict[str, str] | None:
        """Return conditional HTTP headers recorded for a CDN URL, or None if unknown.

        The URL must resolve within this version/locale cache; no request is performed.
        """
        relative = self._relative_for_url(url)
        if relative is None:
            return None
        validator = self._validators.get(relative)
        if not validator:
            return None
        headers: dict[str, str] = {}
        if validator.get("etag"):
            headers["If-None-Match"] = validator["etag"]
        if validator.get("last_modified"):
            headers["If-Modified-Since"] = validator["last_modified"]
        return headers or None

    def _relative_for_url(self, url: str) -> str | None:
        prefix = f"{self.base_url}/{self.version}/"
        localized = f"{prefix}{self.locale.folder}/"
        asset_prefix = f"{self.asset_base_url}/"
        if url.startswith(localized):
            return url[len(localized):]
        if url.startswith(prefix):
            return url[len(prefix):]
        if url.startswith(asset_prefix):
            return "asset:" + url[len(asset_prefix):]
        return None

    def _discover_details(self, manifest: CacheManifest) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for kind in CATALOG_DETAIL_KINDS:
            payload = self._read_cached_json(f"{kind}.json")
            if isinstance(payload, dict):
                found.update((kind, str(identifier)) for identifier in payload)
        maze_versions = self._read_cached_json("maze/version.json")
        if isinstance(maze_versions, dict):
            for values in maze_versions.values():
                if isinstance(values, list):
                    found.update(("maze", str(value)) for value in values)
        peak_versions = self._read_cached_json("peak/version.json")
        if isinstance(peak_versions, dict):
            for values in peak_versions.values():
                if isinstance(values, list):
                    found.update(("maze_peak", str(value)) for value in values)
        for mode in ("maze_extra", "maze_boss"):
            payload = self._read_cached_json(f"{mode}.json")
            if isinstance(payload, dict):
                found.update((mode, str(identifier)) for identifier in payload)
        for kind in sorted({current for current, _ in found}):
            manifest.detail_ids[kind] = sorted(
                identifier for current, identifier in found if current == kind
            )
        self._touch()
        return found

    def _read_cached_json(self, relative: str) -> Any | None:
        path = self.data_dir / relative
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    async def _download_details(
        self,
        manifest: CacheManifest,
        specs: set[tuple[str, str]],
        *,
        refresh: bool = False,
    ) -> None:
        pending: list[Endpoint] = []
        for kind, identifier in sorted(specs):
            endpoint = detail_endpoint(kind, identifier)
            relative = endpoint.key
            path = self.data_dir / relative
            if path.is_file() and not refresh:
                if relative not in manifest.detail_files:
                    manifest.detail_files.append(relative)
                continue
            pending.append(endpoint)
        for index in range(0, len(pending), self.concurrency):
            batch = pending[index:index + self.concurrency]
            await gather_bounded(
                self._download_detail(manifest, endpoint, revalidate=refresh)
                for endpoint in batch
            )
            await self._write_manifest(manifest)
        await self._write_manifest(manifest, force=True)

    async def _download_detail(
        self,
        manifest: CacheManifest,
        endpoint: Endpoint,
        *,
        revalidate: bool = False,
    ) -> None:
        ok = await self._download_endpoint(
            manifest, endpoint, allow_missing=True, revalidate=revalidate
        )
        if ok:
            relative = endpoint.key
            if relative not in manifest.detail_files:
                manifest.detail_files.append(relative)
                self._touch()

    async def _refresh(self, manifest: CacheManifest) -> CacheManifest:
        """Revalidate/download inside the caller-held ``_lock``.

        ``ensure()`` already serializes updates with ``_lock``, so this
        helper must not acquire locks of its own.
        """
        self._touch()
        self._manifest = manifest
        # ``revalidate=True`` still downloads files that are missing, so this
        # covers both a fresh version and an existing cache.
        await self._download_endpoints(manifest, ROOT_ENDPOINTS, revalidate=True)
        await self._download_endpoints(manifest, LOCALIZED_ROOT_ENDPOINTS, revalidate=True)
        await self._download_endpoints(manifest, VERSION_ENDPOINTS, revalidate=True)
        await self._download_localized_diff(manifest)
        specs = self._discover_details(manifest)
        await self._download_details(manifest, specs, refresh=True)
        if self.include_assets:
            manifest = await self._download_assets(
                manifest, revalidate=bool(manifest.assets_complete)
            )
            # Asset failures are pruned per-URL when a retry succeeds; never
            # clear the list wholesale, since an interrupted refresh would
            # otherwise hide genuinely missing files.
        manifest.complete = True
        await self._write_manifest(manifest, force=True)
        return manifest

    async def _download_localized_diff(self, manifest: CacheManifest) -> None:
        """Fetch the optional per-locale changelog without failing the refresh."""
        for endpoint in DIFF_ENDPOINTS:
            path = endpoint.path.format(locale=self.locale.folder)
            relative = path
            destination = self.data_dir / relative
            if destination.is_file():
                continue
            url = f"{self.base_url}/{self.version}/{path}"
            try:
                response = await self.http.get(url, allow_404=True, use_cache=True, cache=self)
            except NanokaHTTPError:
                continue
            if response.status == 404 or not response.body:
                continue
            atomic_write_bytes(destination, response.body)
            self._record_validator(relative, response)
            if relative not in manifest.root_files:
                manifest.root_files.append(relative)
                self._touch()
