"""Offline Light Cone formatting, lifecycle, cache, and rendering regressions."""

import asyncio
import inspect
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image, ImageDraw

from hsr_cards import LCInfoCardResult, get_LC_info, get_character_info
from hsr_cards.nanoka.exceptions import NanokaNotFoundError
from hsr_cards.nanoka.models import LightConeDetail
from hsr_cards.renderer.nanoka.light_cone import (
    GOLD, PATH_LABELS, LightConeData, _font, _rich, ascension_costs, effect_runs,
    layout_runs, level_80_stats, load_light_cone, refinement_description, render_light_cone,
)

FIXTURES = Path(__file__).parent / "fixtures"
MODULE = "hsr_cards.renderer.nanoka.light_cone"


def detail(identifier=23034):
    payload = json.loads((FIXTURES / f"lightcone_{identifier}.json").read_text(encoding="utf-8"))
    return LightConeDetail.model_validate({"id": identifier, **payload})


def card_data(identifier=23034, version="4.7.51", locale="en"):
    cone = detail(identifier)
    return LightConeData(
        identifier=identifier, name=cone.name, version=version, locale=locale,
        detail=cone, stars=cone.stars, path=cone.path_codename,
        effect_name=cone.refinements.name, description=refinement_description(cone),
        stats=level_80_stats(cone), costs=ascension_costs(cone),
        client=SimpleNamespace(close=AsyncMock()),
    )


class FormattingTests(unittest.TestCase):
    def test_user_example_is_expanded_exactly(self):
        expected = (
            "After the wearer uses Skill or Ultimate on one ally character, the wearer regenerates "
            "6/6.5/7/7.5/8 Energy and the ability's target receives 1 stack of \"Hymn\" for 3 turn(s), "
            "stacking up to 3 time(s). Each stack of \"Hymn\" increases its holder's DMG dealt by "
            "15/17.25/19.5/21.75/24%. After every 2 instance(s) of Skill or Ultimate the wearer uses "
            "on one ally character, recovers 1 Skill Point."
        )
        self.assertEqual(refinement_description(detail()), expected)

    def test_percentage_and_decimal_values_are_not_rounded_to_integers(self):
        self.assertIn("16/18/20/22/24%", refinement_description(detail(21018)))
        text = refinement_description(detail())
        self.assertIn("17.25", text)
        self.assertNotIn("3/3/3/3/3", text)
        self.assertNotIn("6.0", text)

    def test_missing_rank_parameters_raise(self):
        cone = detail()
        cone.refinements.level.pop("3")
        with self.assertRaisesRegex(ValueError, "Missing S1-S5"):
            refinement_description(cone)

    def test_level_80_values_match_reference(self):
        self.assertEqual(level_80_stats(detail(23066)), {"hp": 953, "atk": 582, "def": 529})
        self.assertEqual(level_80_stats(detail()), {"hp": 1164, "atk": 476, "def": 529})
        cone = detail()
        cone.stats = cone.stats[:-1]
        with self.assertRaisesRegex(ValueError, "Level-80 stats"):
            level_80_stats(cone)

    def test_ascension_costs_match_reference_and_exclude_leveling_exp(self):
        self.assertEqual(ascension_costs(detail()), {
            2: 385000, 110231: 4, 110232: 12, 110233: 15, 114011: 20, 114012: 20, 114013: 14,
        })

    def test_harmony_and_abundance_labels_are_distinct(self):
        self.assertEqual(PATH_LABELS["en"][detail().path_codename], "Harmony")
        self.assertEqual(PATH_LABELS["en"]["priest"], "Abundance")

    def test_numbers_are_bold_and_colored(self):
        runs = _rich(refinement_description(detail()))
        energy = next(run for run in runs if run.text == "6/6.5/7/7.5/8")
        self.assertTrue(energy.bold)
        self.assertEqual(energy.color, GOLD)
        self.assertTrue(any(run.text == "1" and run.bold for run in runs))
        self.assertEqual("".join(run.text for run in runs), refinement_description(detail()))

    def test_wrapping_preserves_text_and_fits_actual_bold_metrics(self):
        runs = _rich(refinement_description(detail(23066)))
        lines = layout_runs(runs, 920, "en")
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        for line in lines:
            width = sum(draw.textlength(run.text, _font(32, "en", run.bold)) for run in line)
            self.assertLessEqual(width, 920)
        original = refinement_description(detail(23066))
        wrapped = " ".join("".join(run.text for run in line).strip() for line in lines)
        self.assertEqual(original, wrapped)

    def test_comparison_strikes_old_values_and_highlights_new_ones(self):
        before = card_data()
        after = replace(before, description=before.description.replace("6/6.5/7/7.5/8", "7/7.5/8/8.5/9"))
        runs = effect_runs(after, before)
        self.assertTrue(any(run.strike and "6/6.5" in run.text for run in runs))
        self.assertTrue(any(not run.strike and "7/7.5/8/8.5/9" in run.text for run in runs))
        self.assertTrue(any("->" in run.text for run in runs))
        self.assertFalse(any(run.strike for run in effect_runs(before, before)))

    def test_cards_fit_telegram_photo_dimensions_and_save(self):
        for identifier in (23034, 23066):
            image = render_light_cone(card_data(identifier))
            self.assertEqual(image.width, 1080)
            self.assertLessEqual(image.height / image.width, 2)
            self.assertLess(image.width + image.height, 10000)
            self.assertGreaterEqual(image.height, 1440)
            with TemporaryDirectory() as directory:
                path = Path(directory) / "card.png"
                image.save(path)
                with Image.open(path) as opened:
                    self.assertEqual(opened.size, image.size)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_standalone_accepts_same_parameters_as_character_info(self):
        self.assertEqual(inspect.signature(get_LC_info).parameters, inspect.signature(get_character_info).parameters)

    async def test_not_found_closes_client(self):
        client = SimpleNamespace(initialize=AsyncMock(), get_lightcone=AsyncMock(return_value=None), close=AsyncMock())
        with patch(MODULE + ".NanokaClient", return_value=client):
            with self.assertRaises(NanokaNotFoundError):
                await load_light_cone("does not exist")
        client.close.assert_awaited_once()

    async def test_cache_hit_skips_assets_and_render_and_locale_is_in_filename(self):
        data = card_data(locale="zh")
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_light_cone", AsyncMock(return_value=data)) as load, \
             patch(MODULE + "._load_assets", AsyncMock()) as assets, \
             patch(MODULE + ".render_light_cone", return_value=Image.new("RGBA", (1080, 1440))) as render:
            first = await get_LC_info("A Grounded Ascent", "4.7.51", locale="zh", rendered_cache_dir=directory)
            second = await get_LC_info("A Grounded Ascent", "4.7.51", locale="zh", rendered_cache_dir=directory)
            self.assertEqual(render.call_count, 1)
            self.assertEqual(assets.await_count, 1)
            self.assertEqual(first.cache_path, second.cache_path)
            self.assertTrue(first.cache_path.name.endswith("_zh.png"))
            self.assertIsInstance(first, LCInfoCardResult)
            load.assert_awaited_with("A Grounded Ascent", version="4.7.51", locale="zh", cache_dir=None, proxy=None)
        self.assertEqual(data.client.close.await_count, 2)

    async def test_force_refresh_replaces_cached_image(self):
        data = card_data()
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_light_cone", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_light_cone", side_effect=[Image.new("RGBA", (10, 10), "red"), Image.new("RGBA", (10, 10), "blue")]) as render:
            await get_LC_info(23034, rendered_cache_dir=directory)
            result = await get_LC_info(23034, rendered_cache_dir=directory, force_refresh=True)
            self.assertEqual(render.call_count, 2)
            with Image.open(result.cache_path) as image:
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 255, 255))

    async def test_comparison_passes_same_id_and_closes_both_versions(self):
        before, after = card_data(version="4.6.51"), card_data(version="4.6.54")
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_light_cone", AsyncMock(side_effect=[before, after])) as load, \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_light_cone", return_value=Image.new("RGBA", (10, 10))) as render:
            result = await get_LC_info("A Grounded Ascent", ("4.6.51", "4.6.54"), rendered_cache_dir=directory)
            self.assertEqual(result.version, ("4.6.51", "4.6.54"))
            self.assertIn("4.6.51--4.6.54", result.cache_path.name)
            self.assertEqual(load.await_args_list[1].args, (23034,))
            render.assert_called_once_with(after, before)
        before.client.close.assert_awaited_once()
        after.client.close.assert_awaited_once()

    async def test_disabled_cache_never_creates_directory(self):
        data = card_data()
        with TemporaryDirectory() as directory, \
             patch(MODULE + ".load_light_cone", AsyncMock(return_value=data)), \
             patch(MODULE + "._load_assets", AsyncMock()), \
             patch(MODULE + ".render_light_cone", return_value=Image.new("RGBA", (10, 10))):
            target = Path(directory) / "unused"
            result = await get_LC_info(23034, rendered_cache_dir=target, use_rendered_cache=False)
            self.assertFalse(target.exists())
            self.assertIsNone(result.cache_path)
            result.save(Path(directory) / "manual.png")
            self.assertEqual(result.size, (10, 10))

    async def test_second_version_failure_and_cancellation_close_first_client(self):
        for failure in (RuntimeError("failed"), asyncio.CancelledError()):
            before = card_data()
            with patch(MODULE + ".load_light_cone", AsyncMock(side_effect=[before, failure])):
                with self.assertRaises(type(failure)):
                    await get_LC_info(23034, ("4.6.51", "4.6.54"))
            before.client.close.assert_awaited_once()

    async def test_main_client_delegates_the_same_arguments(self):
        with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, {
            "ltoken_v2": "unused", "ltuid_v2": "unused", "default_uid": "800000000",
        }):
            from hsr_cards import HonkaiStarrail
        self.assertEqual(inspect.signature(HonkaiStarrail.get_LC_info), inspect.signature(HonkaiStarrail.get_character_info))
        client = object.__new__(HonkaiStarrail)
        with patch("hsr_cards.renderer.nanoka.get_LC_info", AsyncMock(return_value="card")) as render:
            result = await client.get_LC_info("A Grounded Ascent", ("4.6.51", "4.6.54"), locale="ja",
                                              cache_dir="data", proxy="http://proxy.test", rendered_cache_dir="cards", use_rendered_cache=False)
        self.assertEqual(result, "card")
        render.assert_awaited_once_with("A Grounded Ascent", ("4.6.51", "4.6.54"), locale="ja",
                                       cache_dir="data", proxy="http://proxy.test", rendered_cache_dir="cards", use_rendered_cache=False)


if __name__ == "__main__":
    unittest.main()
