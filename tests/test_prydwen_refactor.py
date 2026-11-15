"""Provider ownership and compatibility regressions using offline fixtures."""
from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from hsr_cards.clients.prydwen import PrydwenClient
from hsr_cards.providers.prydwen.api import PrydwenAPIClient
from hsr_cards.providers.prydwen.models import TierListData


@pytest.mark.parametrize("legacy,modern", [
    ("hsr_cards.prydwen.builds.client", "hsr_cards.clients.prydwen"),
    ("hsr_cards.prydwen.builds.models", "hsr_cards.providers.prydwen.models"),
    ("hsr_cards.prydwen.builds.fetch", "hsr_cards.providers.prydwen.fetch"),
    ("hsr_cards.prydwen.builds.browser_fetch", "hsr_cards.providers.prydwen.browser_fetch"),
    ("hsr_cards.prydwen.builds.nanoka", "hsr_cards.providers.prydwen.assets"),
    ("hsr_cards.prydwen.builds.parse", "hsr_cards.providers.prydwen.parsing.builds"),
    ("hsr_cards.prydwen.builds.render", "hsr_cards.renderer.prydwen.builds.card"),
])
def test_legacy_modules_share_canonical_identity(legacy, modern):
    assert importlib.import_module(legacy) is importlib.import_module(modern)


def test_imports_do_not_discover_cache_paths_or_open_browser(tmp_path):
    script = """
import contextlib
import io
import sys
from pathlib import Path
from unittest.mock import patch

# Dependencies may inspect installation paths; package imports must never discover
# a work/cache directory or launch the explicitly selected browser transport.
import aiohttp, bs4, pydantic
stream = io.StringIO()
with patch.object(Path, 'cwd', side_effect=AssertionError('cwd discovery during import')), \
     patch.object(Path, 'mkdir', side_effect=AssertionError('directory creation during import')), \
     contextlib.redirect_stdout(stream):
    from hsr_cards.clients.prydwen import PrydwenClient
    from hsr_cards.providers.prydwen.api import PrydwenAPIClient
    from hsr_cards.providers.prydwen.parsing.builds import parse_html
assert not stream.getvalue(), stream.getvalue()
assert 'hsr_cards.providers.prydwen.browser_fetch' not in sys.modules
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


def test_query_client_leaves_injected_api_open_and_creates_no_work_tree(tmp_path):
    api = SimpleNamespace(get_redeem_codes=AsyncMock(return_value=["code"]),
                          get_tier_list=AsyncMock(return_value="tiers"), close=AsyncMock())
    client = PrydwenClient(work_dir=tmp_path / "work", build_dir=tmp_path / "builds",
                          nanoka_cache=tmp_path / "catalog", api=api)

    async def run():
        async with client:
            assert await client.get_redeem_codes(timeout=12) == ["code"]
            assert await client.get_tier_list(game_mode="PF", timeout=15, proxy="http://proxy") == "tiers"
        await client.close()

    asyncio.run(run())
    api.get_redeem_codes.assert_awaited_once_with(timeout=12)
    api.get_tier_list.assert_awaited_once_with(game_mode="PF", timeout=15, proxy="http://proxy")
    api.close.assert_not_awaited()
    assert not list(tmp_path.iterdir())


def test_client_closes_its_owned_api_once(tmp_path, monkeypatch):
    import hsr_cards.clients.prydwen as client_module
    api = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(client_module, "PrydwenAPIClient", Mock(return_value=api))
    client = PrydwenClient(work_dir=tmp_path / "work", build_dir=tmp_path / "builds",
                          nanoka_cache=tmp_path / "catalog")

    async def run():
        async with client:
            pass
        await client.close()

    asyncio.run(run())
    api.close.assert_awaited_once()


def test_api_validates_query_before_http_and_resolves_proxy_override(monkeypatch):
    import hsr_cards.providers.prydwen.api as api_module
    html = (Path(__file__).parent / "fixtures/prydwen_tier_list.html").read_text("utf-8")
    fetch = Mock(return_value=html)
    monkeypatch.setattr(api_module, "fetch_html", fetch)
    api = PrydwenAPIClient(proxy="http://default")
    data = asyncio.run(api.get_tier_list(timeout=10))
    assert isinstance(data, TierListData)
    fetch.assert_called_once_with(data.source, 10, "http://default")
    fetch.reset_mock()
    asyncio.run(api.get_tier_list(timeout=10, proxy="http://override"))
    fetch.assert_called_once_with(data.source, 10, "http://override")
    fetch.reset_mock()
    for kwargs in ({"game_mode": "AA"}, {"timeout": 0}, {"timeout": -1}):
        with pytest.raises(ValueError):
            asyncio.run(api.get_tier_list(**kwargs))
    fetch.assert_not_called()


def test_api_build_fetcher_keeps_explicit_transport_and_injected_catalog(tmp_path):
    from hsr_cards.providers.prydwen.fetch import FetchConfig
    catalog = object()
    config = FetchConfig(raw_dir=tmp_path / "raw", transport="browser")
    fetcher = PrydwenAPIClient().build_fetcher(config, nanoka=catalog)
    assert fetcher.config is config
    assert fetcher.nanoka is catalog
    assert fetcher._browser is None
    assert not config.raw_dir.exists()


def test_http_scraper_closes_when_response_is_an_error(monkeypatch):
    import cloudscraper
    from hsr_cards.providers.prydwen.http import fetch_html
    scraper = Mock()
    scraper.proxies = {}
    scraper.__enter__ = Mock(return_value=scraper)
    scraper.__exit__ = Mock(return_value=False)
    scraper.get.return_value = SimpleNamespace(status_code=503, text="unavailable")
    monkeypatch.setattr(cloudscraper, "create_scraper", Mock(return_value=scraper))
    with pytest.raises(RuntimeError, match="503"):
        fetch_html("https://www.prydwen.gg/star-rail/codes", 12, "http://proxy")
    scraper.__exit__.assert_called_once()
    assert scraper.proxies == {"http": "http://proxy", "https": "http://proxy"}


def test_legacy_default_cache_is_resolved_when_requested(tmp_path, monkeypatch):
    from hsr_cards.providers.prydwen import assets
    work = tmp_path / ".hsr_prydwen"
    work.mkdir()
    cache = tmp_path / ".nanoka_cache"
    cache.mkdir()
    nested = tmp_path / "repo"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert assets.DEFAULT_NANOKA_CACHE == cache
    assert assets.NanokaIndex().cache_dir == cache
