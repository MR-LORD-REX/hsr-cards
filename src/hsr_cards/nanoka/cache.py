from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .constants import (
    DEFAULT_ASSET_BASE_URL,
    DEFAULT_BASE_URL,
    DEFAULT_CACHE_DIR,
    DEFAULT_CONCURRENCY,
    DEFAULT_LIVE_VERSION,
    DEFAULT_MANIFEST_URL,
    DEFAULT_STATIC_VERSION,
    GAME_MODE_ALIASES,
    PATH_ALIASES,
)
from .endpoints import (
    CATALOG_DETAIL_KINDS,
    DIFF_ENDPOINTS,
    LOCALIZED_ROOT_ENDPOINTS,
    ROOT_ENDPOINTS,
    VERSION_ENDPOINTS,
    Endpoint,
    detail_endpoint,
)
from .exceptions import NanokaCacheError, NanokaHTTPError
from .http import AsyncHTTP
from .locales import Locale
from .models import AssetInfo, CacheManifest, as_utc

MANIFEST_NAME = "manifest.json"


def default_cache_root() -> Path:
    """The cache lives next to the caller's project root, not the package."""
    return Path.cwd() / DEFAULT_CACHE_DIR


async def gather_bounded(awaitables: Iterable[Any]) -> None:
    """Run awaitables in a task group so failures cancel siblings cleanly."""
    if hasattr(asyncio, "TaskGroup"):
        async with asyncio.TaskGroup() as group:
            for awaitable in awaitables:
                group.create_task(awaitable)
        return
    pending = [asyncio.ensure_future(item) for item in awaitables]
    try:
        await asyncio.gather(*pending)
    except BaseException:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise


class NanokaCache:
    """Versioned, locale-aware JSON + asset cache for static.nanoka.cc."""

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
        return self.root / self.version

    @property
    def locale_dir(self) -> Path:
        return self.version_dir / self.locale.folder

    @property
    def data_dir(self) -> Path:
        return self.locale_dir / "data"

    @property
    def assets_dir(self) -> Path:
        return self.locale_dir / "assets"

    @property
    def manifest_path(self) -> Path:
        return self.locale_dir / MANIFEST_NAME

    async def __aenter__(self) -> "NanokaCache":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http:
            await self.http.close()

    def exists(self) -> bool:
        return self.manifest_path.is_file()

    def read_manifest(self) -> CacheManifest | None:
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

    async def ensure(self, *, force: bool = False, update: bool = False) -> CacheManifest:
        async with self._lock:
            manifest = self.read_manifest()
            if not force and not update and not self.auto_update:
                if manifest and manifest.complete:
                    if not self.include_assets or manifest.assets_complete:
                        return manifest
                    return await self._download_assets(manifest)
                if not manifest and self._pinned_version:
                    raise NanokaCacheError(
                        f"No Nanoka cache for {self.version}/{self.locale.value}; "
                        "call initialize() with network access first"
                    )
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
        return await self.ensure(force=force, update=True)

    async def load_json(self, relative_path: str, *, required: bool = True) -> Any | None:
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
        return self.data_dir / relative_path

    def asset_file(self, relative_path: str) -> Path:
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
        await self.ensure()
        path = self.assets_dir / relative
        if path.is_file():
            return path
        if not download or not self.include_assets:
            return None
        if self._manifest is None:
            self._manifest = self.read_manifest() or self._new_manifest()
        await self._download_asset(self._manifest, f"path:{relative}", relative)
        await self._write_manifest(self._manifest, force=True)
        return path if path.is_file() else None


def shutil_rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def mode_key(value: str) -> str:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if key in GAME_MODE_ALIASES:
        return GAME_MODE_ALIASES[key]
    for alias, canonical in GAME_MODE_ALIASES.items():
        if alias.replace("_", " ") == key.replace("_", " "):
            return canonical
    raise ValueError(
        f"Unknown endgame mode {value!r}; use maze, maze_extra, maze_boss, or maze_peak"
    )


def collect_asset_specs(data_dir: Path) -> dict[str, str]:
    """Build the icon index used by the SDK and future card generators."""
    if not data_dir.is_dir():
        return {}
    specs: dict[str, str] = {}
    character_catalog = _load_json_file(data_dir / "character.json")
    if isinstance(character_catalog, dict):
        for identifier, entry in character_catalog.items():
            if not str(identifier).isdigit():
                continue
            specs[f"character:{identifier}"] = f"avatarshopicon/{identifier}.webp"
            specs[f"avatar:{identifier}"] = f"avatarshopicon/{identifier}.webp"
            specs[f"character_round:{identifier}"] = f"avatarroundicon/{identifier}.webp"
            specs[f"character_drawcard:{identifier}"] = f"avatardrawcard/{identifier}.webp"
            if isinstance(entry, dict):
                element = entry.get("damageType")
                if isinstance(element, str):
                    add_element_spec(element, specs)
                path = entry.get("baseType")
                if isinstance(path, str):
                    add_path_spec(path, specs)
    lightcone_catalog = _load_json_file(data_dir / "lightcone.json")
    if isinstance(lightcone_catalog, dict):
        for identifier in lightcone_catalog:
            if str(identifier).isdigit():
                specs[f"lightcone:{identifier}"] = f"lightconemediumicon/{identifier}.webp"
    relic_catalog = _load_json_file(data_dir / "relicset.json")
    if isinstance(relic_catalog, dict):
        for identifier, entry in relic_catalog.items():
            if isinstance(entry, dict):
                icon = entry.get("icon")
                if isinstance(icon, str):
                    specs[f"relic:{identifier}"] = f"itemfigures/{Path(icon).stem}.webp"
    monster_catalog = _load_json_file(data_dir / "monster.json")
    if isinstance(monster_catalog, dict):
        for identifier, entry in monster_catalog.items():
            if not isinstance(entry, dict):
                continue
            icon = entry.get("icon")
            if isinstance(icon, str):
                specs[f"monster:{identifier}"] = f"monstermiddleicon/{Path(icon).stem}.webp"
            for weakness in entry.get("weak") or []:
                if isinstance(weakness, str):
                    add_element_spec(weakness, specs)
    for key, relative in RELIC_ICON_SPECS.items():
        specs[key] = relative
    for path in data_dir.rglob("*.json"):
        payload = _load_json_file(path)
        if payload is not None:
            _collect_from_payload(payload, specs)
    return specs


RELIC_ICON_SPECS = {
    "relicslot:head": "relicfigures/IconRelicHead.webp",
    "relicslot:hands": "relicfigures/IconRelicHands.webp",
    "relicslot:body": "relicfigures/IconRelicBody.webp",
    "relicslot:feet": "relicfigures/IconRelicFoot.webp",
    "relicslot:planar_sphere": "relicfigures/IconRelicNeck.webp",
    "relicslot:link_rope": "relicfigures/IconRelicGoods.webp",
}


def _load_json_file(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _collect_from_payload(payload: Any, specs: dict[str, str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if isinstance(value, str) and value:
                if lowered in {
                    "icon",
                    "icon_path",
                    "item_icon_path",
                    "item_figure_icon_path",
                    "item_currency_icon_path",
                    "image_path",
                    "max_sp_icon",
                    "item_avatar_icon_path",
                    "icon",
                }:
                    add_asset_spec(value, specs)
                elif lowered in {"damage_type", "damagetype", "damage_type_name"}:
                    add_element_spec(value, specs)
                elif lowered in {"base_type", "basetype"}:
                    add_path_spec(value, specs)
            _collect_from_payload(value, specs)
    elif isinstance(payload, list):
        for value in payload:
            _collect_from_payload(value, specs)


def add_asset_spec(value: str, specs: dict[str, str]) -> None:
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return
    stem = Path(normalized).stem
    if not stem:
        return
    lower = normalized.lower()
    if lower.startswith("spriteoutput/monsterfigure/"):
        relative = f"monstermiddleicon/{stem}.webp"
    elif lower.startswith("spriteoutput/gridfight/equipment/"):
        relative = f"gridfight/equipment/{stem}.webp"
    elif lower.startswith("spriteoutput/gridfight/augment"):
        relative = f"gridfight/augmentbig/{stem}.webp"
    elif lower.startswith("spriteoutput/gridfight/portal/"):
        relative = f"gridfight/portal/{stem}.webp"
    elif lower.startswith(
        (
            "spriteoutput/itemicon/",
            "spriteoutput/itemfigures/",
            "spriteoutput/itemcurrency/",
        )
    ):
        relative = f"itemfigures/{stem}.webp"
    elif lower.startswith("spriteoutput/skillicon/") or stem.lower().startswith(("skillicon_", "icon")):
        relative = f"skillicons/{stem}.webp"
    elif "/" not in normalized and not lower.endswith((".webp", ".png", ".jpg", ".jpeg")):
        return
    else:
        relative = normalized.lstrip("/")
    specs[f"stem:{stem}"] = relative
    specs.setdefault(relative, relative)


def add_element_spec(name: str, specs: dict[str, str]) -> None:
    element = name.strip().lower()
    if element in {"physical", "fire", "ice", "thunder", "wind", "quantum", "imaginary"}:
        specs[f"element:{element}"] = f"element/{element}.webp"


def add_path_spec(name: str, specs: dict[str, str]) -> None:
    codename = name.strip().lower()
    if codename in PATH_ALIASES:
        relative = f"pathicon/{codename}.webp"
        specs[f"path:{codename}"] = relative
        specs[f"path:{PATH_ALIASES[codename]}"] = relative
    elif codename in PATH_ALIASES.values():
        specs[f"path:{codename}"] = f"pathicon/{codename}.webp"


__all__ = [
    "NanokaCache",
    "default_cache_root",
    "collect_asset_specs",
    "atomic_write_bytes",
    "atomic_write_text",
    "mode_key",
]