"""Published version metadata and disk cache manifest models."""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import Field
from ..locales import DEFAULT_LOCALE, Locale

from .common import NanokaModel

class AssetInfo(NanokaModel):
    """Manifest metadata for a cached CDN asset and one of its lookup aliases.

    Track its cache-relative path, source URL, size, validators, and last update;
    optional metadata stays None when the provider does not publish it.
    """
    key: str
    path: str
    url: str
    relative_path: str | None = None
    size: int | None = None
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    updated_at: datetime | None = None

class NanokaVersions(NanokaModel):
    """Published HSR data builds advertised by the Nanoka manifest."""

    versions: list[str] = Field(default_factory=list)
    live_server: str | None = None
    live_beta: str | None = None
    latest: str | None = None

class CacheManifest(NanokaModel):
    """Persisted completeness, version, locale, files, and validators for one cache.

    Track JSON and asset completion separately, with empty collections until
    downloads are recorded. Timestamps use UTC; unknown upstream fields are retained.
    """
    schema_version: int = 2
    version: str
    live_version: str | None = None
    language: Locale = DEFAULT_LOCALE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    complete: bool = False
    assets_complete: bool = False
    root_files: list[str] = Field(default_factory=list)
    detail_files: list[str] = Field(default_factory=list)
    detail_ids: dict[str, list[str]] = Field(default_factory=dict)
    assets: dict[str, AssetInfo] = Field(default_factory=dict)
    asset_failures: list[str] = Field(default_factory=list)
    validators: dict[str, dict[str, str]] = Field(default_factory=dict)

__all__ = ['AssetInfo', 'NanokaVersions', 'CacheManifest']
