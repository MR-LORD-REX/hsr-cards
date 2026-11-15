"""Asset downloads and cache-manifest asset records."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..exceptions import NanokaHTTPError
from ..models import AssetInfo, CacheManifest, as_utc


from .io import gather_bounded, atomic_write_bytes
from .specs import collect_asset_specs


class AssetsMixin:
    """Download and revalidate provider assets without changing their paths."""

    async def _download_assets(
        self, manifest: CacheManifest, *, revalidate: bool = False
    ) -> CacheManifest:
        specs = collect_asset_specs(self.data_dir)
        # Many catalog keys alias the same file (e.g. ``character:1515`` and
        # ``stem:1515``). Keep every alias in the manifest, but download each
        # relative path exactly once.
        by_relative: dict[str, list[str]] = {}
        for key, relative in sorted(specs.items()):
            by_relative.setdefault(relative, []).append(key)
        pending: list[str] = []
        for relative, keys in by_relative.items():
            path = self.assets_dir / relative
            if path.is_file():
                size = path.stat().st_size
                for key in keys:
                    if key not in manifest.assets:
                        manifest.assets[key] = AssetInfo(
                            key=key,
                            path=str(path.relative_to(self.root)),
                            relative_path=relative,
                            url=f"{self.asset_base_url}/{relative}",
                            size=size,
                        )
                        self._touch()
                if not revalidate:
                    continue
            pending.append(relative)
        batch_size = max(self.concurrency, 64)
        for index in range(0, len(pending), batch_size):
            batch = pending[index:index + batch_size]
            await gather_bounded(
                self._download_asset(manifest, by_relative[relative], relative)
                for relative in batch
            )
            await self._write_manifest(manifest)
        manifest.assets_complete = True
        await self._write_manifest(manifest, force=True)
        return manifest

    async def _download_asset(
        self,
        manifest: CacheManifest,
        keys: str | Iterable[str],
        relative: str,
    ) -> None:
        aliases = [keys] if isinstance(keys, str) else list(keys)
        url = f"{self.asset_base_url}/{relative}"
        path = self.assets_dir / relative
        try:
            response = await self.http.get(
                url,
                allow_404=True,
                use_cache=True,
                cache=self,
            )
        except NanokaHTTPError:
            if url not in manifest.asset_failures:
                manifest.asset_failures.append(url)
                self._touch()
            return
        if response.status in {304, 404}:
            if url in manifest.asset_failures:
                manifest.asset_failures.remove(url)
                self._touch()
        if response.status == 304:
            if path.is_file():
                self._record_validator_for_url(url, response)
                if aliases[0] not in manifest.assets:
                    size = path.stat().st_size
                    info = AssetInfo(
                        key=aliases[0],
                        path=str(path.relative_to(self.root)),
                        relative_path=relative,
                        url=url,
                        size=size,
                        etag=response.etag,
                        last_modified=response.last_modified,
                        updated_at=as_utc(),
                    )
                    for key in aliases:
                        manifest.assets[key] = info.model_copy(update={"key": key})
                    self._touch()
                return
            # A validator without its file cannot be used; force a fresh
            # fetch on the next update.
            self._validators.pop(self._relative_for_url(url) or "", None)
            self._touch()
            return
        if response.status == 404 or not response.body:
            if url not in manifest.asset_failures:
                manifest.asset_failures.append(url)
                self._touch()
            return
        if url in manifest.asset_failures:
            manifest.asset_failures.remove(url)
            self._touch()
        atomic_write_bytes(path, response.body)
        info = AssetInfo(
            key=aliases[0],
            path=str(path.relative_to(self.root)),
            relative_path=relative,
            url=url,
            size=path.stat().st_size if path.is_file() else None,
            content_type=response.content_type,
            etag=response.etag,
            last_modified=response.last_modified,
            updated_at=as_utc(),
        )
        for key in aliases:
            manifest.assets[key] = info.model_copy(update={"key": key})
        self._record_validator_for_url(url, response)
        self._touch()

    async def asset(self, relative: str, *, download: bool = True) -> Path | None:
        # ``include_assets`` controls the bulk download during ``ensure()``;
        # an explicit single-asset request should still be able to fetch one
        # file (the character cards rely on this for old, unpinned builds).
        """Return a cached asset path, downloading the relative CDN file when missing.

        download=False skips single-file downloading, but initialization still ensures
        the cache. Explicit downloads work when bulk include_assets=False. Missing
        assets return None; successful downloads update the locale manifest and
        initialization/cache errors propagate.
        """
        await self.ensure()
        path = self.assets_dir / relative
        if path.is_file():
            return path
        if not download:
            return None
        if self._manifest is None:
            self._manifest = self.read_manifest() or self._new_manifest()
        await self._download_asset(self._manifest, f"path:{relative}", relative)
        await self._write_manifest(self._manifest, force=True)
        return path if path.is_file() else None
