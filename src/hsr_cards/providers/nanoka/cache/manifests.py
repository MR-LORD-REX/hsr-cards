"""Version discovery and persisted global/per-locale manifests."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from ..exceptions import NanokaCacheError, NanokaHTTPError
from ..models import CacheManifest, NanokaVersions, as_utc


from .io import MANIFEST_NAME, _version_key, shutil_rmtree, atomic_write_text


class ManifestsMixin:
    """Persist cache metadata and discover published versions."""

    def read_manifest(self) -> CacheManifest | None:
        """Read the active locale manifest, reusing the matching in-memory model.

        Return None for absent/version-mismatched data. Invalid JSON/models raise
        NanokaCacheError; matching metadata updates validators and the live version.
        """
        if self._manifest is not None:
            if (
                self._manifest.version == self.version
                and self._manifest.language == self.locale
            ):
                return self._manifest
            self._manifest = None
            self._validators = {}
        if not self.manifest_path.is_file():
            return None
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest = CacheManifest.model_validate(payload)
        except (OSError, ValueError) as exc:
            raise NanokaCacheError(f"Invalid cache manifest at {self.manifest_path}: {exc}") from exc
        if manifest.version != self.version or manifest.language != self.locale:
            return None
        self.live_version = manifest.live_version or self.live_version
        self._manifest = manifest
        self._validators = dict(manifest.validators)
        return manifest

    def _new_manifest(self) -> CacheManifest:
        return CacheManifest(
            schema_version=2,
            version=self.version,
            live_version=self.live_version,
            language=self.locale,
        )

    async def _write_manifest(self, manifest: CacheManifest, *, force: bool = False) -> None:
        if not force and not self._manifest_dirty and self.manifest_path.is_file():
            return
        manifest.updated_at = as_utc()
        manifest.validators = dict(self._validators)
        payload = manifest.model_dump(mode="json")
        async with self._write_lock:
            atomic_write_text(
                self.manifest_path,
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
            self._manifest_dirty = False
        self._manifest = manifest

    def _touch(self) -> None:
        self._manifest_dirty = True

    async def resolve_version(self) -> str:
        """Resolve the newest published build unless the caller pinned one.

        If the CDN is unreachable but a complete cache exists, keep serving it
        instead of turning every call into a network failure.
        """
        if self._pinned_version:
            return self.version
        try:
            payload = await self.http.get_json(self.manifest_url, allow_404=True)
        except NanokaHTTPError:
            if self.exists():
                return self.version
            raise
        entry = payload.get("hsr") if isinstance(payload, dict) else None
        if not isinstance(entry, dict):
            return self.version
        latest = entry.get("latest")
        live = entry.get("live")
        if isinstance(live, str) and live:
            self.live_version = live
        if isinstance(latest, str) and latest:
            if latest != self.version:
                self._manifest = None
                self._validators = {}
            self.version = latest
        return self.version

    async def write_global_manifest(self, payload: Any) -> None:
        """Cache the root manifest for offline ``get_versions`` calls."""
        if not isinstance(payload, dict):
            return
        def _write():
            atomic_write_text(
                self.root / MANIFEST_NAME,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        await asyncio.to_thread(_write)

    async def versions(self, *, refresh: bool = False) -> NanokaVersions:
        """Return the published HSR builds advertised by the root manifest."""
        payload = None if refresh else self._read_global_manifest()
        if not isinstance(payload, dict):
            try:
                payload = await self.http.get_json(self.manifest_url, allow_404=True)
            except NanokaHTTPError as exc:
                if self.exists():
                    payload = {"hsr": {"latest": self.version, "live": self.live_version}}
                else:
                    raise exc
            if isinstance(payload, dict):
                await self.write_global_manifest(payload)
        entry = payload.get("hsr") if isinstance(payload, dict) else None
        entry = entry if isinstance(entry, dict) else {}
        available = entry.get("available")
        versions = [str(value) for value in available] if isinstance(available, list) else []
        latest = entry.get("latest")
        live = entry.get("live")
        if isinstance(live, str) and live:
            self.live_version = live
        if isinstance(latest, str) and latest:
            latest_value = latest
        elif versions:
            latest_value = max(versions, key=_version_key)
        else:
            latest_value = self.version
        if latest_value and latest_value not in versions:
            versions.append(latest_value)
        beta = max(versions, key=_version_key) if versions else latest_value
        return NanokaVersions(
            versions=sorted(set(versions), key=_version_key),
            live_server=live if isinstance(live, str) else None,
            live_beta=beta,
            latest=latest_value,
        )

    def _read_global_manifest(self) -> Any | None:
        path = self.root / MANIFEST_NAME
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    async def clear_version(self, version: str | None = None) -> None:
        """Remove one complete version tree, or every version when omitted."""
        if version:
            target = self.root / str(version)
            if target.is_dir():
                await asyncio.to_thread(shutil_rmtree, target)
            if self.version == str(version):
                self._manifest = None
                self._validators = {}
            return
        self._manifest = None
        self._validators = {}
        for child in self.root.iterdir() if self.root.is_dir() else ():
            if child.is_dir():
                await asyncio.to_thread(shutil_rmtree, child)
            else:
                try:
                    await asyncio.to_thread(child.unlink)
                except OSError:
                    pass
