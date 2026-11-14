"""Browser-based Prydwen collection.

Prydwen rejects plain HTTP with 403, so every page is rendered with the locally
installed Chrome through Playwright. The build tab is clicked before saving,
which makes the raw HTML self-contained and reviewable without a browser.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from .roster import PRYDWEN_CHARACTERS_URL, RosterEntry, parse_roster_html, write_raw_urls
from .nanoka import NanokaIndex

DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
TEAM_MODES = ("Memory of Chaos", "Pure Fiction", "Apocalyptic Shadow", "Anomaly Arbitration")


@dataclass
class FetchConfig:
    raw_dir: Path
    chrome: Path = DEFAULT_CHROME
    headless: bool = True
    timeout_ms: int = 90_000
    settle_ms: int = 5_000
    proxy: str | None = None


class BrowserPrydwenFetcher:
    def __init__(self, config: FetchConfig):
        self.config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserPrydwenFetcher":
        executable = self.config.chrome
        if not executable.is_file():
            raise FileNotFoundError(f"Chrome executable not found: {executable}")
        self._playwright = await async_playwright().start()
        launch: dict[str, object] = {"headless": self.config.headless, "executable_path": str(executable)}
        if self.config.proxy:
            launch["proxy"] = {"server": self.config.proxy}
        self._browser = await self._playwright.chromium.launch(**launch)
        self._context = await self._browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
            ),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _page(self, url: str) -> Page:
        if not self._context:
            raise RuntimeError("PrydwenFetcher must be used as an async context manager")
        page = await self._context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
        if response is None or response.status >= 400:
            status = response.status if response else "no-response"
            raise RuntimeError(f"Prydwen returned {status} for {url}")
        await page.wait_for_timeout(self.config.settle_ms)
        title = await page.title()
        if "just a moment" in title.casefold() or "attention required" in title.casefold():
            await page.close()
            raise RuntimeError(f"Cloudflare challenge on {url}; save a browser session/cookies")
        return page

    async def roster(self) -> list[RosterEntry]:
        page = await self._page(PRYDWEN_CHARACTERS_URL)
        try:
            await page.wait_for_timeout(1_500)
            html = await page.content()
            self.config.raw_dir.mkdir(parents=True, exist_ok=True)
            (self.config.raw_dir / "characters-index.html").write_text(html, encoding="utf-8", newline="")
            return parse_roster_html(html, NanokaIndex())
        finally:
            await page.close()

    async def raw_urls(self) -> Path:
        entries = await self.roster()
        return write_raw_urls(entries, self.config.raw_dir.parent / "rawUrls.json")

    async def character(self, entry: RosterEntry) -> Path:
        page = await self._page(entry.url)
        try:
            await self._activate_build_tab(page)
            await page.wait_for_timeout(1_500)
            path = self.config.raw_dir / f"{entry.slug}.html"
            html = await page.content()
            path.write_text(html, encoding="utf-8", newline="")
            for index, label in enumerate(TEAM_MODES):
                try:
                    await self._select_team_mode(page, label)
                    await page.wait_for_timeout(1_000)
                    mode_html = await page.content()
                    (self.config.raw_dir / f"{entry.slug}.{index}.html").write_text(mode_html, encoding="utf-8", newline="")
                except Exception:
                    continue
            await self._select_team_mode(page, TEAM_MODES[0])
            await page.wait_for_timeout(600)
            meta = {
                "slug": entry.slug,
                "name": entry.name,
                "url": entry.url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "title": await page.title(),
                "bytes": len(html),
            }
            (self.config.raw_dir / f"{entry.slug}.meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return path
        finally:
            await page.close()

    async def all(self, entries: Iterable[RosterEntry], *, concurrency: int = 2) -> list[Path]:
        self.config.raw_dir.mkdir(parents=True, exist_ok=True)
        semaphore = asyncio.Semaphore(max(1, concurrency))
        results: list[Path] = []

        async def run(entry: RosterEntry) -> None:
            async with semaphore:
                try:
                    results.append(await self.character(entry))
                except Exception as exc:  # collect per character, continue batch
                    error = {"slug": entry.slug, "error": str(exc)}
                    (self.config.raw_dir / f"{entry.slug}.error.json").write_text(
                        json.dumps(error, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )

        await asyncio.gather(*(run(entry) for entry in entries))
        return results

    async def _activate_build_tab(self, page: Page) -> None:
        tabs = page.locator("div.single-tab")
        count = await tabs.count()
        for index in range(count):
            if (await tabs.nth(index).inner_text()).strip().casefold() == "build and teams":
                await tabs.nth(index).click()
                return
        raise RuntimeError("Build and teams tab not found")

    async def _capture_team_modes(self, page: Page) -> None:
        for label in TEAM_MODES[1:]:
            await self._select_team_mode(page, label)
            await page.wait_for_timeout(800)

    async def _select_team_mode(self, page: Page, label: str) -> None:
        switcher = page.locator("div.tier-list-switcher.hsr div.option")
        count = await switcher.count()
        for index in range(count):
            if (await switcher.nth(index).inner_text()).strip() == label:
                await switcher.nth(index).click()
                return