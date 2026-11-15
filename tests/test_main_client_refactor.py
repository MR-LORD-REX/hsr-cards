"""Independent facade/provider contracts and session ownership regressions."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import get_args, get_type_hints
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from hsr_cards import HonkaiStarrail
from hsr_cards.clients.hoyolab import HoYoLABClient
from hsr_cards.providers.hoyolab.api import BaseAPI
from hsr_cards.providers.hoyolab.models import Cookies
from hsr_cards.utils.errors import HSR_Error


def run(awaitable):
    return asyncio.run(awaitable)


def test_main_legacy_import_and_literal_modes_are_stable():
    from hsr_cards.client import HonkaiStarrail as old
    from hsr_cards.clients.main import HonkaiStarrail as new
    from hsr_cards.api.base_api import BaseAPI as old_api
    from hsr_cards.models.auth import Cookies as old_cookies
    assert old is new is HonkaiStarrail
    assert old_api is BaseAPI
    assert old_cookies is Cookies
    assert get_type_hints(new.__init__)["nanoka_client"] is not None
    for method in (new.get_current_endgame_card, new.get_next_endgame_card):
        assert get_args(get_type_hints(method)["game_mode"]) == ("MOC", "PF", "AS", "AA")


def test_uid_free_context_and_close_do_not_construct_providers():
    async def check():
        with patch("hsr_cards.clients.main.HoYoLABClient", side_effect=AssertionError("player client")), \
             patch("hsr_cards.clients.nanoka.NanokaClient", side_effect=AssertionError("catalog client")), \
             patch("hsr_cards.clients.prydwen.PrydwenClient", side_effect=AssertionError("build client")), \
             patch("aiohttp.ClientSession", side_effect=AssertionError("session")):
            async with HonkaiStarrail() as client:
                assert client.uid is None
            await client.close()
    run(check())


def test_uid_free_player_call_fails_before_session_creation():
    async def check():
        with patch("aiohttp.ClientSession", side_effect=AssertionError("session")):
            with pytest.raises(HSR_Error, match="UID is required"):
                await HonkaiStarrail().MOC()
    run(check())


def test_borrowed_clients_are_not_closed_by_the_facade():
    clients = [SimpleNamespace(close=AsyncMock()) for _ in range(3)]
    async def check():
        async with HonkaiStarrail(hoyolab_client=clients[0], nanoka_client=clients[1], prydwen_client=clients[2]):
            pass
    run(check())
    for client in clients:
        client.close.assert_not_awaited()


def test_owned_clients_all_close_when_one_cleanup_fails():
    client = HonkaiStarrail()
    owned = [SimpleNamespace(close=AsyncMock()) for _ in range(3)]
    owned[0].close.side_effect = RuntimeError("cleanup failed")
    client._hoyolab, client._nanoka, client._prydwen = owned
    with pytest.raises(RuntimeError, match="cleanup failed"):
        run(client.close())
    for provider in owned:
        provider.close.assert_awaited_once()


def test_uid_free_tier_render_and_codes_use_borrowed_prydwen_only():
    data = object()
    codes = [object()]
    image = Image.new("RGB", (2, 2))
    provider = SimpleNamespace(get_tier_list=AsyncMock(return_value=data),
                               get_redeem_codes=AsyncMock(return_value=codes), close=AsyncMock())
    renderer = MagicMock()
    renderer.__aenter__ = AsyncMock(return_value=renderer)
    renderer.__aexit__ = AsyncMock(return_value=None)
    renderer.render_tier_list = AsyncMock(return_value=image)
    async def check():
        async with HonkaiStarrail(proxy="http://proxy.test", prydwen_client=provider) as client:
            with patch("hsr_cards.clients.main.TierListRenderer", return_value=renderer) as factory, \
                 patch("hsr_cards.clients.main.HoYoLABClient", side_effect=AssertionError("player client")):
                assert await client.tier_list("PF", raw=True, timeout=8) == (image, data)
                factory.assert_called_once_with(session=None, proxy="http://proxy.test", timeout=8)
                assert await client.redeem_codes() is codes
    run(check())
    provider.get_tier_list.assert_awaited_once_with(game_mode="PF", timeout=8, proxy="http://proxy.test")
    provider.get_redeem_codes.assert_awaited_once_with()
    provider.close.assert_not_awaited()


def test_endgame_and_build_delegates_preserve_borrowed_nanoka_lifecycle():
    nanoka = SimpleNamespace(close=AsyncMock(), character_build=AsyncMock(return_value="build"))
    client = HonkaiStarrail(nanoka_client=nanoka)
    async def check():
        with patch("hsr_cards.renderer.nanoka.get_current_endgame_card", AsyncMock(return_value="cards")) as render:
            assert await client.get_current_endgame_card("AS", (3, 4), force_refresh=True) == "cards"
            assert render.await_args.kwargs["client"] is nanoka
        assert await client.character_build("Acheron", detailed=True) == "build"
        await client.close()
    run(check())
    assert nanoka.character_build.await_args.args == ("Acheron",)
    nanoka.close.assert_not_awaited()


def test_hoyolab_domain_queries_borrow_an_api_and_inherit_cookie_metadata():
    cookies = Cookies(ltoken_v2="test-token", ltuid_v2="test-user")
    api = SimpleNamespace(fetch_moc=AsyncMock(return_value={"data": {}}), close=AsyncMock())
    player = HoYoLABClient("800000000", cookies, api=api)
    client = HonkaiStarrail(hoyolab_client=player)
    assert client.uid == "800000000" and client.cookie is cookies
    async def check():
        async with player:
            assert await player.get_moc("2") == {"data": {}}
        await client.close()
    run(check())
    api.fetch_moc.assert_awaited_once_with("2", server="prod_official_asia", need_all="true")
    api.close.assert_not_awaited()


@pytest.mark.parametrize("uid,server", [("800000000", "prod_official_asia"), ("100000000", "prod_official_asia"),
                                        ("600000000", "prod_official_usa"), ("700000000", "prod_official_eur")])
def test_server_resolution_is_unchanged(uid, server):
    assert HonkaiStarrail(uid)._check_server() == server


@pytest.mark.parametrize("uid,message", [("500000000", "HK,TW"), ("400000000", "Invalid UID")])
def test_unsupported_servers_fail_without_requests(uid, message):
    with pytest.raises(ValueError, match=message):
        HonkaiStarrail(uid)._check_server()


def test_hoyolab_api_borrowed_session_remains_open_and_owned_session_is_closed():
    borrowed = SimpleNamespace(closed=False, close=AsyncMock())
    created = SimpleNamespace(closed=False, close=AsyncMock())
    async def check():
        async with BaseAPI("800000000", session=borrowed) as api:
            assert api.session is borrowed
        with patch("hsr_cards.providers.hoyolab.api.aiohttp.ClientSession", return_value=created) as factory:
            api = BaseAPI("800000000")
            factory.assert_not_called()
            async with api:
                assert api.session is created
            await api.close()
    run(check())
    borrowed.close.assert_not_awaited()
    created.close.assert_awaited_once()


def test_explicit_cookie_calendar_uses_player_uid_and_public_api_uses_configured_uid():
    async def check():
        private = BaseAPI("700000000", cookie={"ltoken_v2": "x", "ltuid_v2": "y"})
        public = BaseAPI("700000000")
        private._request = AsyncMock(return_value={})
        public._request = AsyncMock(return_value={})
        await private.fetch_calendar(server="prod_official_eur")
        private._request.assert_awaited_once_with("ACT_CALENDAR", {"server": "prod_official_eur", "role_id": "700000000"})
        with patch("hsr_cards.providers.hoyolab.api.get_default_uid", return_value="800000001"):
            await public.fetch_calendar(server="prod_official_eur")
        public._request.assert_awaited_once_with("ACT_CALENDAR", {"server": "prod_official_asia", "role_id": "800000001"})
    run(check())

def test_default_asset_update_preserves_bulk_assets_and_build_only_client_is_scoped():
    update_client = SimpleNamespace(update_assets=AsyncMock(), close=AsyncMock())
    build_client = SimpleNamespace(character_build=AsyncMock(return_value="build"), close=AsyncMock())
    async def check():
        with patch("hsr_cards.clients.nanoka.NanokaClient", return_value=update_client) as factory:
            facade = HonkaiStarrail(proxy="http://proxy.test")
            await facade.update_nanoka_assets(version="4.7.51", force=True)
            factory.assert_called_once_with(proxy="http://proxy.test")
            update_client.update_assets.assert_awaited_once_with(version="4.7.51", force=True)
            await facade.close()
        with patch("hsr_cards.clients.nanoka.NanokaClient", return_value=build_client) as factory:
            assert await HonkaiStarrail().character_build("Acheron") == "build"
            factory.assert_called_once_with(proxy=None, include_assets=False)
    run(check())
    update_client.close.assert_awaited_once()
    build_client.close.assert_awaited_once()


def test_cookie_verification_returns_false_without_a_player_uid():
    cookies = Cookies(ltoken_v2="test-token", ltuid_v2="test-user")
    assert run(HonkaiStarrail(cookie=cookies).verify_cookies()) is False
    assert run(HonkaiStarrail().verify_cookies()) is False
