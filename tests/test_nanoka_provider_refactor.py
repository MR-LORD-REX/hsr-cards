"""Offline contracts for Nanoka API/domain separation and resource ownership."""

import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from hsr_cards.clients.nanoka import NanokaClient
from hsr_cards.providers.nanoka.api import NanokaAPIClient
from hsr_cards.providers.nanoka.cache import NanokaCache
from hsr_cards.providers.nanoka.exceptions import NanokaNotFoundError
from hsr_cards.providers.nanoka.locales import Locale
from hsr_cards.providers.nanoka.models import CacheManifest, CharacterSummary


def transport():
    """Fail any unexpected network access while recording transport ownership."""
    return SimpleNamespace(
        get=AsyncMock(side_effect=AssertionError("fixture queries must stay offline")),
        get_json=AsyncMock(side_effect=AssertionError("fixture queries must stay offline")),
        close=AsyncMock(),
    )


def cached_api(tmp_path):
    http = transport()
    cache = NanokaCache(cache_dir=tmp_path, version="test", include_assets=False, http=http)
    cache.data_dir.mkdir(parents=True)
    cache.manifest_path.write_text(
        CacheManifest(version="test", language=Locale.EN, complete=True).model_dump_json(),
        encoding="utf-8",
    )
    return NanokaAPIClient(cache=cache), http


def write_document(api, name, payload):
    path = api.cache.data_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("module", ["cache", "constants", "endpoints", "exceptions", "http", "locales", "models"])
def test_legacy_provider_modules_alias_the_new_implementation(module):
    old = importlib.import_module(f"hsr_cards.nanoka.{module}")
    new = importlib.import_module(f"hsr_cards.providers.nanoka.{module}")
    assert old is new


def test_legacy_client_and_models_keep_type_identity():
    from hsr_cards.nanoka.client import NanokaClient as LegacyClient
    from hsr_cards.nanoka.models import CharacterSummary as LegacySummary
    assert LegacyClient is NanokaClient
    assert LegacySummary is CharacterSummary


def test_legacy_cache_star_exports_keep_atomic_write_helpers():
    cache = importlib.import_module("hsr_cards.nanoka.cache")
    assert {"NanokaCache", "default_cache_root", "collect_asset_specs", "atomic_write_bytes",
            "atomic_write_text", "mode_key"} == set(cache.__all__)


def test_constructor_is_offline_and_preserves_default_cache_paths(tmp_path):
    root = tmp_path / "not-created"
    with patch("aiohttp.ClientSession", side_effect=AssertionError("constructor opened a session")):
        client = NanokaClient(version="test", language="jp", cache_dir=root, include_assets=False)
    assert client.cache_path == root / "test" / "ja"
    assert not root.exists()
    assert client.api_client.cache is client.cache
    asyncio.run(client.close())


def test_domain_context_keeps_injected_api_and_http_open(tmp_path):
    api, http = cached_api(tmp_path)
    api.close = AsyncMock()

    async def run():
        async with NanokaClient(api_client=api) as client:
            assert client.version == "test"
            assert client.language is Locale.EN
            assert client.cache is api.cache
    asyncio.run(run())
    api.close.assert_not_awaited()
    http.close.assert_not_awaited()


def test_domain_context_closes_its_created_api_even_after_failure(tmp_path):
    api, _ = cached_api(tmp_path)
    api.close = AsyncMock()

    async def run():
        with patch("hsr_cards.clients.nanoka.NanokaAPIClient", return_value=api):
            with pytest.raises(RuntimeError, match="query failed"):
                async with NanokaClient():
                    raise RuntimeError("query failed")
    asyncio.run(run())
    api.close.assert_awaited_once()


def test_api_closes_only_resources_it_created(tmp_path):
    http = transport()
    with patch("hsr_cards.providers.nanoka.api.AsyncHTTP", return_value=http):
        api = NanokaAPIClient(cache_dir=tmp_path, include_assets=False)
    asyncio.run(api.close())
    http.close.assert_awaited_once()


def test_api_keeps_injected_cache_and_transport_open(tmp_path):
    api, http = cached_api(tmp_path)
    api.cache.close = AsyncMock()
    asyncio.run(api.close())
    api.cache.close.assert_not_awaited()
    http.close.assert_not_awaited()


def test_api_keeps_injected_http_open_when_it_created_the_cache(tmp_path):
    http = transport()
    api = NanokaAPIClient(cache_dir=tmp_path, http=http, include_assets=False)
    asyncio.run(api.close())
    http.close.assert_not_awaited()


def test_catalog_and_domain_client_synchronize_the_resolved_version(tmp_path):
    api, _ = cached_api(tmp_path)
    api.cache.load_json = AsyncMock(return_value={"upstream": True})
    api.cache.version = "new-build"
    assert asyncio.run(api.catalog("character.json")) == {"upstream": True}
    assert api.version == "new-build"
    client = NanokaClient(api_client=api)
    api.cache.version = "newer-build"
    assert asyncio.run(client._read_json("item_all.json", required=False)) == {"upstream": True}
    assert client.version == "newer-build"


def test_domain_character_queries_preserve_filtering_details_and_extra_fields(tmp_path):
    api, http = cached_api(tmp_path)
    write_document(api, "character.json", {
        "1001": {"en": "Released", "rank": "CombatPowerAvatarRarityType4", "release": 100,
                 "baseType": "knight", "damageType": "Ice"},
        "1002": {"en": "New Character", "ja": "New JP", "rank": "CombatPowerAvatarRarityType5",
                 "baseType": "knight", "damageType": "Ice", "future_catalog_field": 7},
        "1003": {"en": "Other", "rank": "CombatPowerAvatarRarityType5", "baseType": "mage", "damageType": "Fire"},
    })
    write_document(api, "character/1002.json", {
        "name": "Detailed Character", "future_detail_field": {"preserved": True},
    })
    client = NanokaClient(api_client=api)

    async def run():
        entries = await client.list_characters(element="ice", path="Preservation", rarity=5)
        assert [item.id for item in entries] == [1002]
        assert entries[0].future_catalog_field == 7
        wrapped = await client.get_character("New JP", include_details=True)
        assert wrapped.id == 1002
        assert wrapped.summary is not None
        assert wrapped.detail.future_detail_field == {"preserved": True}
        assert await client.get_character("missing") is None
        assert [item.id for item in await client.list_characters(include_beta=False)] == [1001]
    asyncio.run(run())
    http.get.assert_not_awaited()
    http.get_json.assert_not_awaited()


@pytest.mark.parametrize("mode,folder", [("MOC", "maze"), ("PF", "story"), ("AS", "boss"), ("AA", "peak")])
def test_endgame_raw_payloads_keep_list_shape_and_unmodeled_fields(tmp_path, mode, folder):
    api, http = cached_api(tmp_path)
    payload = [{"id": 10, "unmodeled_effect": {"param_list": [0.3, 3]}}]
    write_document(api, f"{folder}/20.json", payload)
    client = NanokaClient(api_client=api)
    assert asyncio.run(client.get_endgame_payload(20, mode=mode)) == payload
    http.get.assert_not_awaited()


def test_detail_and_optional_documents_preserve_missing_data_contract(tmp_path):
    api, http = cached_api(tmp_path)
    assert asyncio.run(api.document("optional.json", required=False)) is None
    assert asyncio.run(api.catalog("optional.json", required=False)) == {}
    assert asyncio.run(api.detail("character", 1001, required=False)) is None
    with pytest.raises(NanokaNotFoundError):
        asyncio.run(api.detail("character", 1001))
    with pytest.raises(ValueError, match="Unknown endgame mode"):
        asyncio.run(api.get_endgame_payload(1, mode="unknown"))
    http.get.assert_not_awaited()


def test_optional_item_catalog_falls_back_to_item_json(tmp_path):
    api, _ = cached_api(tmp_path)
    write_document(api, "item.json", {"5": {"ItemName": "Fallback item", "Rarity": "Normal"}})
    client = NanokaClient(api_client=api)
    items = asyncio.run(client.list_items())
    assert [(item.id, item.name) for item in items] == [(5, "Fallback item")]


def test_domain_asset_fetch_delegates_to_api_and_synchronizes_version(tmp_path):
    api, _ = cached_api(tmp_path)
    expected = Path(tmp_path) / "asset.webp"

    async def fetch(relative, *, refresh=False):
        api.version = "new-build"
        return expected

    api.fetch_asset = AsyncMock(side_effect=fetch)
    client = NanokaClient(api_client=api)
    assert asyncio.run(client.fetch_asset("monster/example.webp", refresh=True)) == expected
    api.fetch_asset.assert_awaited_once_with("monster/example.webp", refresh=True)
    assert client.version == "new-build"


def test_versions_and_build_switching_preserve_cached_metadata_contract(tmp_path):
    api, http = cached_api(tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps({"hsr": {
        "available": ["4.7", "4.7.51", "4.6.54"], "live": "4.7", "latest": "4.7.51",
    }}), encoding="utf-8")
    api.cache.update = AsyncMock()
    client = NanokaClient(api_client=api)

    async def run():
        versions = await client.get_versions()
        assert versions.versions == ["4.6.54", "4.7", "4.7.51"]
        assert versions.live_server == "4.7"
        assert versions.live_beta == "4.7.51"
        with pytest.raises(ValueError, match="Unknown Nanoka version"):
            await client.update_assets(version="missing")
        assert client.version == "test"
        api.cache.update.assert_not_awaited()
        api.cache._validators = {"old.json": {"etag": "old"}}
        assert await client.update_assets(version="4.7.51", force=True) is client
        assert client.version == api.version == api.cache.version == "4.7.51"
        assert client.cache_path == tmp_path / "4.7.51" / "en"
        assert api.cache._pinned_version is True
        assert api.cache._validators == {}
    asyncio.run(run())
    api.cache.update.assert_awaited_once_with(force=True)
    http.get_json.assert_not_awaited()


def test_cache_clear_preserves_other_versions_then_clears_all_metadata(tmp_path):
    api, _ = cached_api(tmp_path)
    client = NanokaClient(api_client=api)
    other = tmp_path / "other" / "en" / "data"
    other.mkdir(parents=True)
    (other / "keep.json").write_text("{}", encoding="utf-8")
    global_manifest = tmp_path / "manifest.json"
    global_manifest.write_text("{}", encoding="utf-8")

    async def run():
        await client.clear_cache(version="test")
        assert not (tmp_path / "test").exists()
        assert (other / "keep.json").is_file()
        assert global_manifest.is_file()
        await client.clear_cache()
        assert not list(tmp_path.iterdir())
    asyncio.run(run())
