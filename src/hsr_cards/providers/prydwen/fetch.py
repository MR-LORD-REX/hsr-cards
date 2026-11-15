"""Cache-first collection of public Prydwen HTML, separate from offline parsing.

HTTP is the default. Explicit browser collection additionally captures client-side
team modes; it is optional and never invoked by parsing or card rendering.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

import cloudscraper
from bs4 import BeautifulSoup

from .assets import NanokaIndex
from .parsing.roster import PRYDWEN_CHARACTERS_URL, RosterEntry, parse_roster_html, write_raw_urls

DEFAULT_CHROME = None


@dataclass
class FetchConfig:
    """Options for explicit public-page collection, including cache root and transport timeouts."""
    raw_dir: Path
    chrome: Path | None = DEFAULT_CHROME
    headless: bool = True
    timeout_ms: int = 30_000
    settle_ms: int = 1_500
    proxy: str | None = None
    transport: str = "http"
    refresh: bool = False
    retries: int = 2


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="")
    temporary.replace(path)


def valid_html(html: str, *, index: bool = False) -> bool:
    """Never accept a challenge, error page, or client-only empty shell as a cache."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
    if any(marker in title for marker in ("just a moment", "attention required", "access denied", "404", "not found")):
        return False
    if index:
        return bool(soup.select("a[href*='/star-rail/characters/']"))
    return bool(soup.select_one(".character-top h1") and soup.select_one(".character-intro, .content-header"))


class PrydwenFetcher:
    """Collect cache-first character HTML through scoped HTTP sessions or an explicit browser."""
    def __init__(self, config: FetchConfig, *, nanoka: NanokaIndex | None = None):
        """Store collection options and a read-only Nanoka index; request sessions open lazily."""
        self.config = config
        self.nanoka = nanoka if nanoka is not None else NanokaIndex()
        self._local = threading.local()
        self._sessions: list = []
        self._browser = None
        self.failures: list[dict[str, str]] = []
        self.cached = 0
        self.downloaded = 0

    async def __aenter__(self) -> "PrydwenFetcher":
        """Create the raw cache and open only the configured explicit transport.

        Unknown transports raise ValueError; browser launch failures propagate."""
        self.config.raw_dir.mkdir(parents=True, exist_ok=True)
        if self.config.transport == "browser":
            from .browser_fetch import BrowserPrydwenFetcher
            self._browser = BrowserPrydwenFetcher(self.config)
            await self._browser.__aenter__()
        elif self.config.transport != "http":
            raise ValueError(f"Unknown transport: {self.config.transport}")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Close the operation-owned browser and every worker HTTP session."""
        if self._browser:
            await self._browser.__aexit__(exc_type, exc, tb)
        for session in self._sessions:
            session.close()

    def _session(self):
        if not hasattr(self._local, "session"):
            session = cloudscraper.create_scraper()
            if self.config.proxy:
                session.proxies.update({"http": self.config.proxy, "https": self.config.proxy})
            self._sessions.append(session)
            self._local.session = session
        return self._local.session

    async def _download(self, url: str, *, index: bool = False) -> tuple[str, dict]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "www.prydwen.gg" or not parsed.path.startswith("/star-rail/characters"):
            raise ValueError("Expected a public Prydwen Star Rail character URL")
        for attempt in range(self.config.retries + 1):
            try:
                response = await asyncio.to_thread(self._session_get, url)
                response.raise_for_status()
                html = response.content.decode("utf-8")
                if not valid_html(html, index=index):
                    raise ValueError(f"No character HTML in response for {url}")
                return html, {
                    "url": url,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "transport": "cloudscraper",
                    "status": response.status_code,
                    "http_last_modified": response.headers.get("Last-Modified"),
                    "etag": response.headers.get("ETag"),
                }
            except Exception:
                if attempt == self.config.retries:
                    raise
                await asyncio.sleep(min(2 ** attempt, 4))
        raise RuntimeError("unreachable")

    def _session_get(self, url: str):
        return self._session().get(url, timeout=self.config.timeout_ms / 1000)

    def _cached(self, path: Path, *, index: bool = False) -> bool:
        if self.config.refresh or not path.is_file():
            return False
        try:
            raw = path.read_bytes()
            meta_path = path.with_suffix(".meta.json")
            if meta_path.is_file():
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                expected = metadata.get("html_sha256")
                if expected and hashlib.sha256(raw).hexdigest() != expected:
                    return False
            return valid_html(raw.decode("utf-8"), index=index)
        except (OSError, UnicodeError, ValueError):
            return False

    def _write_meta(self, path: Path, html: str, meta: dict) -> None:
        meta.update({"bytes": len(html.encode("utf-8")), "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(), "raw_file": path.name})
        _atomic_text(path.with_suffix(".meta.json"), json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    def _adopt_meta(self, path: Path, url: str) -> None:
        if not path.with_suffix(".meta.json").is_file():
            self._write_meta(path, path.read_bytes().decode("utf-8"), {
                "url": url,
                "fetched_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "transport": "existing-cache",
            })

    async def roster(self) -> list[RosterEntry]:
        """Read a valid cached character index or download it and return parsed roster entries.

        Refresh policy follows config; source HTML and provenance metadata are written
        locally on download. HTTP, parsing, and filesystem errors propagate."""
        path = self.config.raw_dir / "characters-index.html"
        if self._cached(path, index=True):
            html = path.read_bytes().decode("utf-8")
            self._adopt_meta(path, PRYDWEN_CHARACTERS_URL)
        else:
            html, meta = await self._download(PRYDWEN_CHARACTERS_URL, index=True)
            entries = parse_roster_html(html, self.nanoka)
            if not entries:
                raise ValueError("Prydwen character index contained no roster entries")
            _atomic_text(path, html)
            self._write_meta(path, html, meta)
        return parse_roster_html(html, self.nanoka)

    async def raw_urls(self) -> Path:
        """Collect the roster and write rawUrls.json beside the raw cache, returning its path."""
        return write_raw_urls(await self.roster(), self.config.raw_dir.parent / "rawUrls.json")

    async def character(self, entry: RosterEntry) -> Path:
        """Return cached or collected HTML for one validated roster slug.

        Writes source metadata and updates cache/download counters. Invalid slugs raise
        ValueError; request, browser, and filesystem errors propagate."""
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", entry.slug):
            raise ValueError(f"Invalid character slug: {entry.slug}")
        path = self.config.raw_dir / f"{entry.slug}.html"
        if self._cached(path):
            self._adopt_meta(path, entry.url)
            self.cached += 1
            return path
        if self._browser:
            await self._browser.character(entry)
            html = path.read_bytes().decode("utf-8")
            if not valid_html(html):
                raise ValueError(f"Invalid browser HTML for {entry.slug}")
            meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
            meta["transport"] = "browser"
        else:
            html, meta = await self._download(entry.url)
            _atomic_text(path, html)
        self._write_meta(path, html, {**meta, "slug": entry.slug, "name": entry.name})
        path.with_suffix(".error.json").unlink(missing_ok=True)
        self.downloaded += 1
        return path

    async def all(self, entries: Iterable[RosterEntry], *, concurrency: int = 2) -> list[Path]:
        """Collect a roster concurrently and return available HTML paths in input order.

        Concurrency is bounded to one through four. Individual failures are retained
        in failures and error JSON; writes a manifest and keeps successful results."""
        entries = list(entries)
        semaphore = asyncio.Semaphore(max(1, min(concurrency, 4)))
        self.failures = []

        async def run(entry: RosterEntry) -> Path | None:
            async with semaphore:
                try:
                    path = await self.character(entry)
                    print(f"cached {entry.slug}", flush=True)
                    return path
                except Exception as exc:
                    error = {"slug": entry.slug, "url": entry.url, "attempted_at": datetime.now(timezone.utc).isoformat(), "error": str(exc)}
                    self.failures.append(error)
                    _atomic_text(self.config.raw_dir / f"{entry.slug}.error.json", json.dumps(error, ensure_ascii=False, indent=2) + "\n")
                    print(f"FAILED {entry.slug}: {exc}", flush=True)
                    return None

        paths = await asyncio.gather(*(run(entry) for entry in entries))
        manifest = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "expected": len(entries), "available": sum(path is not None for path in paths),
            "cached": self.cached, "downloaded": self.downloaded,
            "characters": [entry.slug for entry in entries],
            "failures": sorted(self.failures, key=lambda item: item["slug"]),
        }
        _atomic_text(self.config.raw_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        return [path for path in paths if path is not None]