"""Browser defaults work without a hardcoded Windows installation."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from hsr_cards.clients.prydwen import PrydwenClient
from hsr_cards.providers.prydwen import paths
from hsr_cards.providers.prydwen.fetch import FetchConfig


def test_default_browser_path_is_unset_until_browser_mode_is_used(tmp_path):
    config = FetchConfig(tmp_path)
    assert config.chrome is None
    client = PrydwenClient(work_dir=tmp_path / "work", nanoka_cache=tmp_path / "cache", api=object())
    assert client.fetch_config.chrome is None
    assert not client.work_dir.exists()


def test_browser_discovery_uses_chromium_from_path(tmp_path, monkeypatch):
    binary = tmp_path / "chromium"
    monkeypatch.setattr(paths.shutil, "which", lambda name: str(binary) if name == "chromium" else None)
    assert paths.discover_chrome() == binary


def test_browser_discovery_uses_windows_installation_environment(tmp_path, monkeypatch):
    binary = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"test executable")
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(paths, "os", SimpleNamespace(environ={"PROGRAMFILES": str(tmp_path)}))
    monkeypatch.setattr(paths.shutil, "which", lambda name: None)
    assert paths.discover_chrome() == binary


def test_browser_discovery_uses_mac_app_location(monkeypatch):
    binary = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(paths.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda path: path == binary)
    assert paths.discover_chrome() == binary


def test_browser_discovery_allows_playwright_when_nothing_is_installed(monkeypatch):
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(paths.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda path: False)
    assert paths.discover_chrome() is None


@pytest.fixture
def mocked_playwright(monkeypatch):
    module = pytest.importorskip("hsr_cards.providers.prydwen.browser_fetch")
    context = SimpleNamespace(close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    driver = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)), stop=AsyncMock())
    start = AsyncMock(return_value=driver)
    monkeypatch.setattr(module, "async_playwright", lambda: SimpleNamespace(start=start))
    discover = Mock(return_value=None)
    monkeypatch.setattr(module, "discover_chrome", discover)
    return SimpleNamespace(module=module, driver=driver, browser=browser, context=context, start=start, discover=discover)


def test_missing_system_browser_uses_playwright_managed_chromium(mocked_playwright, tmp_path):
    runtime = mocked_playwright

    async def run():
        async with runtime.module.BrowserPrydwenFetcher(FetchConfig(tmp_path, proxy="http://proxy")):
            pass

    asyncio.run(run())
    runtime.driver.chromium.launch.assert_awaited_once_with(headless=True, proxy={"server": "http://proxy"})
    runtime.context.close.assert_awaited_once()
    runtime.browser.close.assert_awaited_once()
    runtime.driver.stop.assert_awaited_once()


def test_explicit_browser_path_overrides_discovery(mocked_playwright, tmp_path):
    runtime = mocked_playwright
    binary = tmp_path / "custom-chrome"
    binary.write_bytes(b"test executable")

    async def run():
        async with runtime.module.BrowserPrydwenFetcher(FetchConfig(tmp_path, chrome=binary)):
            pass

    asyncio.run(run())
    runtime.discover.assert_not_called()
    runtime.driver.chromium.launch.assert_awaited_once_with(headless=True, executable_path=str(binary))


def test_discovered_browser_is_passed_to_playwright(mocked_playwright, tmp_path):
    runtime = mocked_playwright
    runtime.discover.return_value = tmp_path / "chromium"

    async def run():
        async with runtime.module.BrowserPrydwenFetcher(FetchConfig(tmp_path)):
            pass

    asyncio.run(run())
    runtime.driver.chromium.launch.assert_awaited_once_with(headless=True, executable_path=str(runtime.discover.return_value))


def test_invalid_explicit_browser_path_is_reported_before_driver_start(mocked_playwright, tmp_path):
    runtime = mocked_playwright

    async def run():
        async with runtime.module.BrowserPrydwenFetcher(FetchConfig(tmp_path, chrome=tmp_path / "missing")):
            pass

    with pytest.raises(FileNotFoundError, match="Chrome executable not found"):
        asyncio.run(run())
    runtime.start.assert_not_awaited()
    runtime.discover.assert_not_called()


def test_failed_launch_releases_playwright_driver(mocked_playwright, tmp_path):
    runtime = mocked_playwright
    runtime.driver.chromium.launch.side_effect = RuntimeError("browser dependency missing")

    async def run():
        async with runtime.module.BrowserPrydwenFetcher(FetchConfig(tmp_path)):
            pass

    with pytest.raises(RuntimeError, match="browser dependency missing"):
        asyncio.run(run())
    runtime.driver.stop.assert_awaited_once()
