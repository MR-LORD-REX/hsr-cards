"""Self-contained PF/AS regressions against the supplied Nanoka references."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageDraw

from hsr_cards.nanoka.exceptions import NanokaNotFoundError
from hsr_cards.nanoka.models import MazeSchedule, MonsterDetail
from hsr_cards.renderer.nanoka import endgames as cards

FIXTURE = json.loads((Path(__file__).parent / "fixtures/endgame_reference.json").read_text(encoding="utf-8"))


class OfflineClient:
    version = "4.7.51"

    def __init__(self, **kwargs):
        self.cache = SimpleNamespace(
            load_json=AsyncMock(side_effect=lambda name, required=False: FIXTURE.get(name)),
            asset_file=lambda relative: Path("not-downloaded") / relative,
        )
        self.initialize = AsyncMock()
        self._prepare = AsyncMock()
        self.close = AsyncMock()
        self.fetch_asset = AsyncMock(return_value=None)
        self._detail = AsyncMock(side_effect=self.detail)

    async def get_endgame_payload(self, identifier, *, mode="maze", refresh=False):
        return await self._detail(mode, identifier)

    async def detail(self, mode, identifier):
        for season in FIXTURE["seasons"].values():
            if season["schedule"]["id"] == identifier:
                return season["payload"]
        raise NanokaNotFoundError(mode, identifier)

    async def get_monster_detail(self, identifier):
        payload = FIXTURE["monsters"].get(str(identifier))
        if payload is None:
            raise NanokaNotFoundError("monster", identifier)
        return MonsterDetail.model_validate(payload)

    async def list_monsters(self):
        return [SimpleNamespace(id=int(key), child=[item["id"] for item in value["child"]])
                for key, value in FIXTURE["monsters"].items()]


def schedule(mode):
    return MazeSchedule.model_validate(FIXTURE["seasons"][mode]["schedule"])


async def floor_data(mode, floor=4):
    payload = FIXTURE["seasons"][mode]["payload"]
    return await cards.build_floor_data(
        OfflineClient(), schedule(mode), floor, cards.group_floor_records(payload["level"])[floor],
        mode=mode, status="LIVE", season_payload=payload,
    )


class ReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pf_uses_infinite_rosters_counts_scaling_and_third_node(self):
        data = await floor_data("PF")
        self.assertEqual(data.season_name, "Imagined Words")
        self.assertEqual(data.conditions, ["Gain 60000 points", "Gain 75000 points", "Gain 90000 points"])
        self.assertEqual(data.special, "Gain 99000 points")
        self.assertEqual([node.elements for node in data.nodes], [
            ["ice", "thunder"], ["fire", "imaginary"], ["physical", "ice"],
        ])
        expected = [
            [[437713, 227611, 262628, 525255], [245119, 280136, 14444523], [2738332, 1932940, 66444812]],
            [[437713, 175085, 175085, 525255], [280136, 393942, 14444523], [2416175, 1610783, 66444812]],
            [[481484, 202223, 105927, 577781], [455221, 341416, 18777882], [2696311, 1862906, 80889341]],
        ]
        for node, hp_waves in zip(data.nodes, expected):
            self.assertEqual([[int(cards.format_hp(monster.hp).replace(",", "")) for monster in wave] for wave in node.waves], hp_waves)
            self.assertEqual([monster.count for monster in node.waves[0]], [1, 14, 13, 2])
            self.assertEqual([monster.count for monster in node.waves[1]], [20, 20, 1])
        corroded = [monster for wave in data.nodes[1].waves for monster in wave if monster.corrosion_hp is not None]
        self.assertEqual([cards.format_hp(monster.corrosion_hp) for monster in corroded], ["52,526", "4,333,357", "724,853"])
        self.assertEqual(data.nodes[1].corrosion_targets, [])
        self.assertEqual([effect.name for effect in data.season_effects], ["Toccata", "Mirthful Cadence", "Fugato"])
        self.assertIn("400%", data.season_effects[-1].text)

    async def test_as_boss_bars_corrosion_and_starward_effects(self):
        data = await floor_data("AS")
        self.assertEqual(data.conditions, ["Gain 6000 points", "Gain 7800 points", "Gain 9900 points"])
        self.assertEqual(data.special, "Gain 10200 points")
        self.assertEqual([node.waves[0][0].hp_text for node in data.nodes], [
            "HP 13,275,627 x2", "HP 10,888,876 x2", "HP 10,646,901 x2",
        ])
        self.assertEqual(data.nodes[0].waves[0][0].icon_asset, "monstermiddleicon/Monster_2004010.webp")
        self.assertEqual(data.nodes[2].label, "STARWARD MODE")
        self.assertEqual(data.nodes[2].elements, ["physical", "fire", "wind", "quantum"])
        self.assertEqual([cards.format_hp(target.bonus_hp) for target in data.nodes[0].corrosion_targets], ["374,841", "468,552"])
        self.assertEqual([len(node.season_effects) for node in data.nodes], [3, 3, 3])
        self.assertEqual([len(node.stage_effects) for node in data.nodes], [4, 4, 4])
        self.assertIn("50% less DMG", data.nodes[0].stage_effects[0].text)
        self.assertIn("100%", data.nodes[0].stage_effects[0].text)
        self.assertIn("60%", data.nodes[2].stage_effects[-1].text)
        self.assertIn("25%", data.buff_text)
        self.assertIn("15%", data.buff_text)

    async def test_floor_three_has_two_nodes_and_three_waves_per_pf_node(self):
        for mode in ("PF", "AS"):
            data = await floor_data(mode, 3)
            self.assertEqual([node.number for node in data.nodes], [1, 2])
            self.assertIsNone(data.special)
            if mode == "PF":
                self.assertEqual([len(node.waves) for node in data.nodes], [3, 3])

    async def test_render_contains_every_effect_and_stays_in_bounds(self):
        for mode in ("PF", "AS"):
            for floor in (3, 4):
                data = await floor_data(mode, floor)
                texts = []
                drawn = []
                original = ImageDraw.ImageDraw.text

                def capture(draw, xy, text, *args, **kwargs):
                    texts.append(str(text))
                    drawn.append((draw._image.size, draw.textbbox(xy, text, font=kwargs.get("font"), anchor=kwargs.get("anchor"))))
                    return original(draw, xy, text, *args, **kwargs)

                with patch.object(ImageDraw.ImageDraw, "text", capture):
                    image = cards.render_floor_card(data)
                self.assertEqual(image.width, 1080)
                self.assertLessEqual(sum(image.size), 10000)
                self.assertLessEqual(max(image.size) / min(image.size), 20)
                rendered = "\n".join(texts)
                self.assertNotRegex(rendered, r"#\d|<unbreak>|<color")
                for node in data.nodes:
                    for effect in [*node.season_effects, *node.stage_effects]:
                        self.assertIn(effect.name, rendered)
                for (width, height), (left, top, right, bottom) in drawn:
                    self.assertGreaterEqual(left, 0)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(right, width)
                    self.assertLessEqual(bottom, height)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_modes_dispatch_and_normalize(self):
        for mode, canonical in (("PF", "maze_extra"), ("AS", "maze_boss")):
            client = OfflineClient()
            live = schedule(mode).model_copy(update={"live_begin": "2020-01-01", "live_end": "2099-01-01"})
            client.get_current_endgame = AsyncMock(return_value=SimpleNamespace(schedule=live))
            with patch.object(cards, "NanokaClient", return_value=client), patch.object(cards, "_season_card", AsyncMock(return_value="rendered")) as render:
                self.assertEqual(await cards.get_current_endgame_card(f" {mode.lower()} ", 4), "rendered")
                self.assertEqual(client.get_current_endgame.await_args.args, (canonical,))
                self.assertEqual(render.await_args.args[:3], (mode, live, 4))
            client.close.assert_awaited_once()

    async def test_season_loading_defaults_and_cached_results(self):
        for mode, canonical in (("PF", "maze_extra"), ("AS", "maze_boss")):
            with TemporaryDirectory() as directory:
                client = OfflineClient()
                kwargs = dict(locale="en", cache_dir=None, proxy=None, rendered_cache_dir=directory, use_rendered_cache=True, force_refresh=False)
                with patch.object(cards, "NanokaClient", return_value=client):
                    result = await cards._season_card(mode, schedule(mode), None, **kwargs)
                    self.assertEqual([card.floor for card in result.cards], [3, 4])
                    client._detail.assert_awaited_with(canonical, schedule(mode).id)
                    self.assertTrue(all(card.cache_path.is_file() for card in result.cards))
                    with patch.object(cards, "render_floor_card", side_effect=AssertionError("cached images should be reused")):
                        cached = await cards._season_card(mode, schedule(mode), None, **kwargs)
                    self.assertEqual([card.image.size for card in result.cards], [card.image.size for card in cached.cards])
                    with patch.object(cards, "render_floor_card", return_value=Image.new("RGBA", (10, 10))) as render:
                        await cards._season_card(mode, schedule(mode), 4, **{**kwargs, "force_refresh": True})
                        render.assert_called_once()
                    with self.assertRaisesRegex(ValueError, f"{mode}.*no floor"):
                        await cards._season_card(mode, schedule(mode), 99, **kwargs)

    async def test_next_ignores_test_dates_and_preserves_unscheduled_seasons(self):
        for mode in ("PF", "AS"):
            client = OfflineClient()
            current = MazeSchedule(id=10, live_begin="2020-01-01", live_end="2090-01-01")
            scheduled = MazeSchedule(id=11, live_begin="2090-01-01", live_end="2091-01-01")
            unscheduled = MazeSchedule(id=12, begin="2010-01-01", end="2010-02-01")
            old = MazeSchedule(id=9, live_begin="2010-01-01", live_end="2011-01-01")
            client.get_current_endgame = AsyncMock(return_value=SimpleNamespace(id=current.id))
            client.list_maze = AsyncMock(return_value=[unscheduled, old, scheduled, current])
            with patch.object(cards, "NanokaClient", return_value=client), patch.object(cards, "_season_card", AsyncMock(side_effect=lambda mode, season, *args, **kwargs: season.id)) as render:
                self.assertEqual(await cards.get_next_endgame_card(mode, look_ahead="max"), [11, 12])
                self.assertEqual(await cards.get_next_endgame_card(mode), 11)
            self.assertEqual(cards.season_status(unscheduled), "UNSCHEDULED")

    async def test_next_without_a_live_season_keeps_the_first_future_season(self):
        client = OfflineClient()
        earliest = MazeSchedule(id=10, live_begin="2090-01-01", live_end="2091-01-01")
        later = MazeSchedule(id=11, live_begin="2091-01-01", live_end="2092-01-01")
        client.list_maze = AsyncMock(return_value=[later, earliest])
        with patch.object(cards, "NanokaClient", return_value=client), patch.object(cards, "_season_card", AsyncMock(side_effect=lambda mode, season, *args, **kwargs: season.id)):
            self.assertEqual(await cards.get_next_endgame_card("PF"), 10)

    async def test_empty_next_and_invalid_modes_fail_clearly(self):
        client = OfflineClient()
        client.get_current_endgame = AsyncMock(return_value=None)
        client.list_maze = AsyncMock(return_value=[])
        with patch.object(cards, "NanokaClient", return_value=client):
            with self.assertRaisesRegex(ValueError, "No upcoming PF"):
                await cards.get_next_endgame_card("PF")
            self.assertEqual(await cards.get_next_endgame_card("AS", look_ahead="max"), [])
        for render in (cards.get_current_endgame_card, cards.get_next_endgame_card):
            with self.assertRaises(ValueError):
                await render("unknown")
            with self.assertRaisesRegex(NotImplementedError, "deferred"):
                await render("AA")


if __name__ == "__main__":
    unittest.main()
