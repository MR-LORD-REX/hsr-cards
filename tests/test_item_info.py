"""Offline regressions for item descriptions, sources, artwork, and lifecycle."""

import asyncio
import inspect
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

from hsr_cards import ItemInfoCardResult, get_character_info, get_item_info
from hsr_cards.nanoka.exceptions import NanokaNotFoundError
from hsr_cards.nanoka.models import ItemSummary, NamedEntry
from hsr_cards.renderer.nanoka.item import (
    ItemData, item_asset, load_item, render_item, source_rows,
)
from hsr_cards.renderer.nanoka.light_cone import _clean

FIXTURES = Path(__file__).parent / "fixtures"
MODULE = "hsr_cards.renderer.nanoka.item"


def summary(identifier=223):
    payload = json.loads((FIXTURES / f"item_{identifier}.json").read_text(encoding="utf-8"))
    return ItemSummary.from_entry(identifier, payload)


def card_data(identifier=223, version="4.7.51", locale="en"):
    item = summary(identifier)
    return ItemData(
        identifier=identifier, name=_clean(item.name, locale), version=version, locale=locale,
        summary=item, description=_clean(item.item_desc or item.item_bg_desc, locale),
        background=_clean(item.item_bg_desc, locale),
        purpose="Light Cone EXP Material" if identifier == 223 else "Premium Currency",
        main_type=item.item_main_type, sub_type=item.item_sub_type,
        sources={entry.id: _clean(entry.desc, locale) for entry in item.item_comefrom if entry.desc},
        client=SimpleNamespace(close=AsyncMock()),
    )


def sdk_client(item):
    return SimpleNamespace(
        initialize=AsyncMock(), close=AsyncMock(), version="4.7.51",
        get_item=AsyncMock(return_value=item),
    )


class ItemTests(unittest.TestCase):
    def test_sdk_sources_are_typed_and_optional(self):
        item = summary()
        self.assertIsInstance(item.item_comefrom[0], NamedEntry)
        self.assertEqual(item.item_comefrom[0].desc, "Calyx: Backwater Pass")
        self.assertEqual(ItemSummary(id=223).item_comefrom, [])

    def test_figure_artwork_uses_actual_asset_id(self):
        self.assertEqual(item_asset(summary()), "itemfigures/223.webp")
        self.assertEqual(item_asset(summary(1)), "itemfigures/900001.webp")
        item = ItemSummary(id=800, item_icon_path="SpriteOutput/ItemIcon/Other.png")
        self.assertEqual(item_asset(item), "itemfigures/Other.webp")

    def test_source_comparisons_keep_removed_and_changed_entries(self):
        before = replace(card_data(), sources={1: "Calyx: Backwater Pass", 2: "Embers Exchange", 3: "Forgotten Hall"})
        after = replace(before, sources={1: "Calyx: Great Mine", 3: "Forgotten Hall", 4: "Mission rewards"})
        rows = {identifier: (status, runs) for identifier, status, runs in source_rows(after, before)}
        self.assertEqual({key: value[0] for key, value in rows.items()}, {
            1: "CHANGED", 2: "REMOVED", 3: "", 4: "ADDED",
        })
        self.assertTrue(any(run.strike for run in rows[1][1]))
        self.assertIn("Great Mine", "".join(run.text for run in rows[1][1]))
        self.assertTrue(all(run.strike for run in rows[2][1]))

    def test_readable_layout_grows_for_long_descriptions(self):
        ordinary = render_item(card_data())
        self.assertEqual(ordinary.size, (1080, 1350))
        long = replace(card_data(), description="Long item description. " * 120)
        self.assertGreater(render_item(long).height, ordinary.height)
        empty = replace(card_data(1), description="", background="", sources={})
        self.assertEqual(render_item(empty).width, 1080)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "item.png"
            ordinary.save(path)
            with Image.open(path) as reopened:
                self.assertEqual(reopened.size, ordinary.size)


class ItemLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_signature_matches_character_info(self):
        self.assertEqual(inspect.signature(get_item_info).parameters, inspect.signature(get_character_info).parameters)

    async def test_loader_prefers_gameplay_description_and_preserves_sources(self):
        client = sdk_client(summary())
        with patch(MODULE + ".NanokaClient", return_value=client) as factory:
            data = await load_item("Refined Aether", locale="jp", cache_dir="data", proxy="http://proxy.test")
        self.assertEqual(data.locale, "ja")
        self.assertEqual(data.description, "Enhancement material for Light Cones, provides 6000 Light Cone EXP.")
        self.assertIn("A canister of aether", data.background)
        self.assertNotIn("<", data.background)
        self.assertNotIn("\\n", data.background)
        self.assertIn("{TextID#FloorName_20503001}", data.sources[7])
        self.assertEqual(len(data.sources), 6)
        factory.assert_called_once_with(version=None, language="ja", cache_dir="data", proxy="http://proxy.test", include_assets=False)
        client.get_item.assert_awaited_once_with("Refined Aether")
        client.close.assert_not_awaited()

    async def test_loader_handles_lore_only_items_and_empty_sources(self):
        item = summary(1)
        item.item_comefrom = [NamedEntry(id=1, desc=None), NamedEntry(id=2, desc=" ")]
        client = sdk_client(item)
        with patch(MODULE + ".NanokaClient", return_value=client):
            data = await load_item(1)
        self.assertEqual(data.description, _clean(item.item_bg_desc))
        self.assertTrue(data.description)
        self.assertEqual(data.sources, {})

    async def test_missing_items_and_loader_failures_close_client(self):
        for payload, failure in ((None, NanokaNotFoundError), (summary(), RuntimeError)):
            client = sdk_client(payload)
            if failure is RuntimeError:
                client.initialize.side_effect = RuntimeError("offline")
            with patch(MODULE + ".NanokaClient", return_value=client):
                with self.assertRaises(failure):
                    await load_item("missing")
            client.close.assert_awaited_once()

    async def test_cache_skips_assets_and_retains_metadata(self):
        data = card_data(locale="zh")
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_item", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock()) as assets, \
             patch(MODULE + ".render_item", return_value=Image.new("RGBA", (1080, 1350))) as render:
            first = await get_item_info(223, locale="zh", rendered_cache_dir=directory)
            second = await get_item_info(223, locale="zh", rendered_cache_dir=directory)
            self.assertEqual(render.call_count, 1)
            self.assertEqual(assets.await_count, 1)
            self.assertEqual(first.cache_path, second.cache_path)
            self.assertTrue(first.cache_path.name.endswith("_zh.png"))
            self.assertIsInstance(second, ItemInfoCardResult)
            self.assertEqual(second.item, data.name)
            self.assertEqual(second.description, data.description)
            self.assertEqual(second.background, data.background)
            self.assertEqual(second.rarity, 4)
            self.assertEqual(second.sources, list(data.sources.values()))
            self.assertEqual(second.main_type, "Material")
            self.assertEqual(second.sub_type, "EquipmentExp")
        self.assertEqual(data.client.close.await_count, 2)

    async def test_cache_distinguishes_items_with_identical_names(self):
        first = card_data()
        second = replace(card_data(), identifier=224, summary=summary().model_copy(update={"id": 224}))
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_item", AsyncMock(side_effect=[first, second])), \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_item", return_value=Image.new("RGBA", (10, 10))) as render:
            a = await get_item_info(223, rendered_cache_dir=directory)
            b = await get_item_info(224, rendered_cache_dir=directory)
            self.assertNotEqual(a.cache_path, b.cache_path)
            self.assertEqual(render.call_count, 2)

    async def test_force_refresh_and_disabled_cache(self):
        data = card_data()
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_item", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_item", return_value=Image.new("RGBA", (10, 10))) as render:
            await get_item_info(223, rendered_cache_dir=directory)
            await get_item_info(223, rendered_cache_dir=directory, force_refresh=True)
            self.assertEqual(render.call_count, 2)
            unused = Path(directory) / "unused"
            result = await get_item_info(223, rendered_cache_dir=unused, use_rendered_cache=False)
            self.assertFalse(unused.exists())
            self.assertIsNone(result.cache_path)
            result.save(Path(directory) / "manual.png")
            self.assertEqual(result.size, (10, 10))

    async def test_comparison_uses_stable_item_id_and_both_versions(self):
        before, after = card_data(version="4.6.51"), card_data(version="4.6.54")
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_item", AsyncMock(side_effect=[before, after])) as load, \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_item", return_value=Image.new("RGBA", (10, 10))) as render:
            result = await get_item_info("Refined Aether", ("4.6.51", "4.6.54"), rendered_cache_dir=directory)
            self.assertEqual(load.await_args_list[1].args, (223,))
            self.assertEqual(result.version, ("4.6.51", "4.6.54"))
            self.assertIn("4.6.51--4.6.54", result.cache_path.name)
            render.assert_called_once_with(after, before)
        before.client.close.assert_awaited_once()
        after.client.close.assert_awaited_once()

    async def test_failures_and_cancellation_release_clients(self):
        for failure in (RuntimeError("failed"), asyncio.CancelledError()):
            before = card_data()
            with patch(MODULE + ".load_item", AsyncMock(side_effect=[before, failure])):
                with self.assertRaises(type(failure)):
                    await get_item_info(223, ("4.6.51", "4.6.54"))
            before.client.close.assert_awaited_once()
        data = card_data()
        with patch(MODULE + ".load_item", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock(side_effect=RuntimeError("offline"))):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                await get_item_info(223, use_rendered_cache=False)
        data.client.close.assert_awaited_once()

    async def test_invalid_version_count_fails_before_loading(self):
        with patch(MODULE + ".load_item", AsyncMock()) as load:
            with self.assertRaises(ValueError):
                await get_item_info(223, ("4.6", "4.7", "4.8"))
            load.assert_not_awaited()

    async def test_main_client_arguments_and_delegation(self):
        with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, {
            "ltoken_v2": "unused", "ltuid_v2": "unused", "default_uid": "800000000",
        }):
            from hsr_cards import HonkaiStarrail
        self.assertEqual(inspect.signature(HonkaiStarrail.get_item_info), inspect.signature(HonkaiStarrail.get_character_info))
        client = object.__new__(HonkaiStarrail)
        with patch("hsr_cards.renderer.nanoka.get_item_info", AsyncMock(return_value="card")) as render:
            result = await client.get_item_info("Refined Aether", ("4.6.51", "4.6.54"), locale="ja", cache_dir="data",
                                                proxy="http://proxy.test", rendered_cache_dir="cards", use_rendered_cache=False)
        self.assertEqual(result, "card")
        render.assert_awaited_once_with("Refined Aether", ("4.6.51", "4.6.54"), locale="ja", cache_dir="data",
                                       proxy="http://proxy.test", rendered_cache_dir="cards", use_rendered_cache=False)


if __name__ == "__main__":
    unittest.main()
