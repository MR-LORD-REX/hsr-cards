"""Offline regressions for relic sets, planar ornaments, and card lifecycle."""

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

from hsr_cards import RelicInfoCardResult, get_relic_info, get_character_info
from hsr_cards.nanoka.exceptions import NanokaNotFoundError
from hsr_cards.nanoka.models import RelicPart, RelicSetDetail
from hsr_cards.renderer.nanoka.relic import (
    RelicData, _load_assets, effect_description, effect_rows, load_relic,
    part_asset, part_rows, render_relic,
)

FIXTURES = Path(__file__).parent / "fixtures"
MODULE = "hsr_cards.renderer.nanoka.relic"


def detail(identifier=134):
    payload = json.loads((FIXTURES / f"relicset_{identifier}.json").read_text(encoding="utf-8"))
    return RelicSetDetail.model_validate({"id": identifier, **payload})


def card_data(identifier=134, version="4.7.51", locale="en"):
    relic = detail(identifier)
    return RelicData(
        identifier=identifier, name=relic.name, version=version, locale=locale, detail=relic,
        effects={effect.pieces: effect_description(effect) for effect in relic.effects},
        parts=relic.piece_list, set_type="cavern" if identifier == 134 else "planar",
        icon_path="itemfigures/71061.webp", client=SimpleNamespace(close=AsyncMock()),
    )


class RelicTests(unittest.TestCase):
    def test_reference_effects_resolve_exactly(self):
        data = card_data()
        self.assertEqual(data.effects, {
            2: "Increases CRIT DMG by 16%.",
            4: "Increases DMG dealt by the wearer's Basic ATK by 36%. When the wearer uses Basic ATK, increases the wearer's ATK by 20%, lasting for 2 turn(s).",
        })

    def test_planar_thresholds_do_not_gain_percent_signs(self):
        fleet = card_data(302)
        self.assertEqual(list(fleet.effects), [2])
        self.assertIn("SPD reaches 120 or higher", fleet.effects[2])
        self.assertNotIn("120%", fleet.effects[2])
        self.assertIn("12%", fleet.effects[2])
        arena = card_data(309)
        self.assertIn("70%", arena.effects[2])

    def test_full_piece_ids_resolve_to_the_correct_slots(self):
        self.assertEqual([p.slot for p in detail().piece_list], ["head", "hands", "body", "feet"])
        self.assertEqual([p.slot for p in detail(309).piece_list], ["planar_sphere", "link_rope"])
        self.assertEqual(RelicPart(id=1).slot, "head")
        self.assertIsNone(RelicPart().slot)
        self.assertIsNone(RelicPart(id=31347).slot)

    def test_piece_assets_are_distinct_and_follow_nanoka_paths(self):
        self.assertEqual([part_asset(134, p) for p in detail().piece_list], [
            f"relicfigures/IconRelic_134_{slot}.webp" for slot in range(1, 5)
        ])
        self.assertEqual(part_asset(309, detail(309).piece_list[1]), "relicfigures/IconRelic_309_6.webp")
        custom = RelicPart(id=31341, icon="SpriteOutput/RelicFigures/Custom.png")
        self.assertEqual(part_asset(134, custom), "relicfigures/Custom.webp")

    def test_missing_effect_parameters_raise(self):
        effect = detail().effects[0]
        effect.param_list = []
        with self.assertRaisesRegex(ValueError, "Missing parameter #1"):
            effect_description(effect)

    def test_comparisons_preserve_removed_and_added_effects(self):
        before = card_data()
        after = replace(before, effects={2: "Increases CRIT DMG by 18%.", 3: "Increases ATK by 10%."})
        rows = {count: (status, runs) for count, status, runs in effect_rows(after, before)}
        self.assertEqual([rows[n][0] for n in (2, 3, 4)], ["CHANGED", "ADDED", "REMOVED"])
        self.assertTrue(any(run.strike and "16%" in run.text for run in rows[2][1]))
        self.assertTrue(any(not run.strike and "18%" in run.text for run in rows[2][1]))
        self.assertTrue(all(run.strike for run in rows[4][1]))

    def test_piece_comparisons_keep_names_and_removed_slots(self):
        before = card_data()
        renamed = before.parts[0].model_copy(update={"name": "New Headpiece"})
        after = replace(before, parts=[renamed, *before.parts[1:3]])
        rows = part_rows(after, before)
        self.assertEqual([row[1] for row in rows], ["CHANGED", "", "", "REMOVED"])
        self.assertTrue(any(run.strike for run in rows[0][2]))
        self.assertIn("New Headpiece", "".join(run.text for run in rows[0][2]))
        self.assertEqual(rows[-1][0].slot, "feet")

    def test_missing_icons_still_render_all_names_and_bonuses(self):
        for identifier, expected in ((134, (1080, 1350)), (309, (1080, 1080))):
            image = render_relic(card_data(identifier))
            self.assertEqual(image.size, expected)
            self.assertLess(image.width + image.height, 10000)
            self.assertLess(image.height / image.width, 2)
            with TemporaryDirectory() as directory:
                path = Path(directory) / "card.png"
                image.save(path)
                with Image.open(path) as saved:
                    self.assertEqual(saved.size, expected)

    def test_long_comparison_text_grows_without_shrinking_body_font(self):
        before = card_data()
        after = replace(before, effects={2: "New bonus. " * 80, 4: before.effects[4]})
        self.assertGreater(render_relic(after, before).height, 1350)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_standalone_arguments_match_character_info(self):
        self.assertEqual(inspect.signature(get_relic_info).parameters, inspect.signature(get_character_info).parameters)

    async def test_loader_uses_sdk_type_locale_and_slot_order(self):
        relic = detail(309)
        client = SimpleNamespace(initialize=AsyncMock(), close=AsyncMock(), version="4.7.51",
                                 get_relic=AsyncMock(return_value=SimpleNamespace(
                                     summary=SimpleNamespace(id=309, icon=relic.icon, display_name=lambda locale: "Localized Set"), detail=relic)))
        with patch(MODULE + ".NanokaClient", return_value=client) as factory:
            data = await load_relic("Rutilant Arena", locale="jp", proxy="http://proxy.test")
        self.assertEqual((data.name, data.set_type, data.locale), ("Localized Set", "planar", "ja"))
        self.assertEqual([p.slot for p in data.parts], ["planar_sphere", "link_rope"])
        factory.assert_called_once_with(version=None, language="ja", cache_dir=None, proxy="http://proxy.test", include_assets=False)
        client.get_relic.assert_awaited_once_with("Rutilant Arena")
        client.close.assert_not_awaited()

    async def test_unknown_or_incomplete_set_closes_client(self):
        for payload in (None, SimpleNamespace(summary=SimpleNamespace(id=134), detail=RelicSetDetail(id=134))):
            client = SimpleNamespace(initialize=AsyncMock(), get_relic=AsyncMock(return_value=payload), close=AsyncMock())
            with patch(MODULE + ".NanokaClient", return_value=client):
                with self.assertRaises((NanokaNotFoundError, ValueError)):
                    await load_relic("missing")
            client.close.assert_awaited_once()

    async def test_assets_use_each_pieces_own_image(self):
        data = card_data()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            Image.new("RGBA", (32, 32), "blue").save(path)
            data.client.fetch_asset = AsyncMock(return_value=path)
            await _load_assets(data)
        urls = [call.args[0] for call in data.client.fetch_asset.await_args_list]
        self.assertEqual(len(urls), 5)
        self.assertIn("relicfigures/IconRelic_134_4.webp", urls)
        self.assertEqual(set(data.icons), {"head", "hands", "body", "feet"})
        self.assertIsNotNone(data.icon)

    async def test_cache_hit_skips_asset_download_and_render(self):
        data = card_data(locale="zh")
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_relic", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock()) as assets, \
             patch(MODULE + ".render_relic", return_value=Image.new("RGBA", (1080, 1350))) as render:
            first = await get_relic_info(134, locale="zh", rendered_cache_dir=directory)
            second = await get_relic_info(134, locale="zh", rendered_cache_dir=directory)
            self.assertEqual(render.call_count, 1)
            self.assertEqual(assets.await_count, 1)
            self.assertEqual(first.cache_path, second.cache_path)
            self.assertTrue(first.cache_path.name.endswith("_zh.png"))
            self.assertIsInstance(second, RelicInfoCardResult)
            self.assertEqual(second.effects, data.effects)
            self.assertEqual([p.id for p in second.parts], [p.id for p in data.parts])
        self.assertEqual(data.client.close.await_count, 2)

    async def test_force_refresh_and_disabled_cache(self):
        data = card_data()
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_relic", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_relic", return_value=Image.new("RGBA", (10, 10))) as render:
            await get_relic_info(134, rendered_cache_dir=directory)
            await get_relic_info(134, rendered_cache_dir=directory, force_refresh=True)
            self.assertEqual(render.call_count, 2)
            unused = Path(directory) / "unused"
            result = await get_relic_info(134, rendered_cache_dir=unused, use_rendered_cache=False)
            self.assertFalse(unused.exists())
            self.assertIsNone(result.cache_path)
            result.save(Path(directory) / "manual.png")
            self.assertEqual(result.size, (10, 10))

    async def test_comparison_resolves_second_version_by_stable_id(self):
        before, after = card_data(version="4.6.51"), card_data(version="4.6.54")
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_relic", AsyncMock(side_effect=[before, after])) as load, \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_relic", return_value=Image.new("RGBA", (10, 10))) as render:
            result = await get_relic_info("The Edacious Heretic", ("4.6.51", "4.6.54"), rendered_cache_dir=directory)
            self.assertEqual(load.await_args_list[1].args, (134,))
            self.assertEqual(result.version, ("4.6.51", "4.6.54"))
            self.assertIn("4.6.51--4.6.54", result.cache_path.name)
            render.assert_called_once_with(after, before)
        before.client.close.assert_awaited_once()
        after.client.close.assert_awaited_once()

    async def test_failures_and_cancellation_release_both_clients(self):
        for failure in (RuntimeError("failed"), asyncio.CancelledError()):
            before = card_data()
            with patch(MODULE + ".load_relic", AsyncMock(side_effect=[before, failure])):
                with self.assertRaises(type(failure)):
                    await get_relic_info(134, ("4.6.51", "4.6.54"))
            before.client.close.assert_awaited_once()
        data = card_data()
        with patch(MODULE + ".load_relic", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock(side_effect=RuntimeError("offline"))):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                await get_relic_info(134, use_rendered_cache=False)
        data.client.close.assert_awaited_once()

    async def test_invalid_version_count_rejected_before_loading(self):
        with patch(MODULE + ".load_relic", AsyncMock()) as load:
            with self.assertRaises(ValueError):
                await get_relic_info(134, ("4.6", "4.7", "4.8"))
            load.assert_not_awaited()

    async def test_main_client_has_same_arguments_and_delegates(self):
        with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, {
            "ltoken_v2": "unused", "ltuid_v2": "unused", "default_uid": "800000000",
        }):
            from hsr_cards import HonkaiStarrail
        self.assertEqual(inspect.signature(HonkaiStarrail.get_relic_info), inspect.signature(HonkaiStarrail.get_character_info))
        client = object.__new__(HonkaiStarrail)
        with patch("hsr_cards.renderer.nanoka.get_relic_info", AsyncMock(return_value="card")) as render:
            value = await client.get_relic_info("Set", ("4.6.51", "4.6.54"), locale="ja", cache_dir="data",
                                                proxy="http://proxy.test", rendered_cache_dir="cards", use_rendered_cache=False)
        self.assertEqual(value, "card")
        render.assert_awaited_once_with("Set", ("4.6.51", "4.6.54"), locale="ja", cache_dir="data",
                                       proxy="http://proxy.test", rendered_cache_dir="cards", use_rendered_cache=False)


if __name__ == "__main__":
    unittest.main()
