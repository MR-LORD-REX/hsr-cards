"""Offline regressions for MOC, PF, and AS endgame floor cards."""

import asyncio
import inspect
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

from hsr_cards import HonkaiStarrail
from hsr_cards.nanoka.exceptions import NanokaNotFoundError
from hsr_cards.nanoka.models import MazeSchedule, MonsterDetail, StageEvent
from hsr_cards.renderer.nanoka.endgames import (
    EndgameCardResult,
    EndgameFloorCard,
    HpBar,
    MonsterInfo,
    build_floor_data,
    continue_floor_index,
    format_hp,
    get_current_endgame_card,
    get_next_endgame_card,
    group_floor_records,
    invasion_ratio,
    monster_hp_values,
    normalize_floors,
    render_floor_card,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "fixtures"
FIXTURE = json.loads((DATA / "moc_reference.json").read_text(encoding="utf-8"))
MODULE = "hsr_cards.renderer.nanoka.endgames"


def load_json(relative):
    if relative == "maze/1036.json":
        return FIXTURE["records"]
    if relative.startswith("monster/"):
        return FIXTURE["monsters"][Path(relative).stem]
    return FIXTURE[relative]


def floor_records(identifier=5512):
    records = [record for record in load_json("maze/1036.json") if int(record.get("id", 0)) == identifier]
    if identifier == 5512:
        records.extend(
            record for record in load_json("maze/1036.json") if int(record.get("pre_id", 0) or 0) == identifier
        )
    return records


def stage_event(record, key):
    items = record.get(key) or []
    return StageEvent.model_validate(items[0])


def ratios():
    return (
        load_json("HardLevelGroup.json"),
        load_json("EliteGroup.json"),
        load_json("monstervalue.json"),
    )


class FloorShapeTests(unittest.TestCase):
    def test_floor_defaults_and_parameter_expansion(self):
        self.assertEqual(normalize_floors("MOC", None), [11, 12])
        self.assertEqual(normalize_floors("PF", None), [3, 4])
        self.assertEqual(normalize_floors("AS", None), [3, 4])
        self.assertEqual(normalize_floors("MOC", 12), [12])
        self.assertEqual(normalize_floors("MOC", [12, 11, 12]), [11, 12])
        with self.assertRaises(ValueError):
            normalize_floors("XX", None)

    def test_continuation_records_merge_into_the_main_floor(self):
        grouped = group_floor_records(load_json("maze/1036.json"))
        self.assertEqual(sorted(grouped), list(range(1, 13)))
        self.assertEqual([int(record["id"]) for record in grouped[12]], [5512, 5513])
        self.assertEqual(continue_floor_index(12, {"name": "Survival of the Fittest (XII)"}), 12)


class HpTests(unittest.TestCase):
    def test_corrosion_uses_the_second_buff_parameter(self):
        record = load_json("maze/1036.json")[-1]
        event = stage_event(record, "event_id_list")
        self.assertAlmostEqual(invasion_ratio(event), 0.30)

    def test_phase_hp_matches_live_moc_values(self):
        hard, elite, values = ratios()
        judge = stage_event(load_json("maze/1036.json")[-1], "event_id_list")
        detail = MonsterDetail.model_validate(load_json("monster/4064010.json"))
        bars = monster_hp_values(judge, 4064010, detail, hard, elite, values)
        self.assertEqual([round(bar.amount) for bar in bars], [7258991, 7258991])
        self.assertEqual(MonsterInfo(4064010, "Judge", None, bars[0].amount, [], bars).hp_text, "HP 7,258,991 x2")

        hoolay = MonsterInfo(0, "Hoolay", None, 0, [], [HpBar(6241196, 1), HpBar(6241196, 2)])
        self.assertEqual(hoolay.hp_text, "HP 6,241,196 x2")
        unequal = MonsterInfo(0, "Yabuli", None, 0, [], [HpBar(5106433, 1), HpBar(10212866, 2)])
        self.assertEqual(unequal.hp_text, "P1 5,106,433 / P2 10,212,866")
        self.assertEqual(format_hp(4085146.2), "4,085,146")

    def test_corrosion_targets_exclude_unaffected_monsters(self):
        record = load_json("maze/1036.json")[-1]
        event = stage_event(record, "event_id_list")
        affected = set(event.invasion.all_monster_ids)
        self.assertEqual(affected, {4064010, 4062010, 4063010})
        self.assertNotIn(2013020, affected)


class RenderTests(unittest.TestCase):
    def test_card_is_telegram_sized_and_has_no_trailing_void(self):

        class OfflineClient:
            version = "4.7.51"
            cache = SimpleNamespace(
                load_json=AsyncMock(side_effect=lambda name, required=False: load_json(name)),
                asset_file=lambda relative: DATA / relative,
            )

            async def get_monster_detail(self, identifier):
                if str(identifier) not in FIXTURE["monsters"]:
                    raise NanokaNotFoundError("monster", identifier)
                payload = load_json(f"monster/{identifier}.json")
                return MonsterDetail.model_validate(payload)

            async def list_monsters(self):
                return [SimpleNamespace(id=int(key), child=[item["id"] for item in value["child"]])
                        for key, value in FIXTURE["monsters"].items()]

        season = MazeSchedule(id=1036, name="Survival of the Fittest")
        data = asyncio.run(build_floor_data(OfflineClient(), season, 12, floor_records(), mode="MOC", status="LIVE"))
        node3 = next(node for node in data.nodes if node.number == 3)
        self.assertEqual([target.identifier for target in node3.corrosion_targets], [4064010, 4062010, 4063010])
        self.assertEqual([round(target.bonus_hp) for target in node3.corrosion_targets], [2177697, 201639, 1290487])
        self.assertTrue(all(target.bonus_ratio == 0.3 for target in node3.corrosion_targets))
        image = render_floor_card(data)
        self.assertEqual(image.width, 1080)
        self.assertLessEqual(sum(image.size), 10000)
        self.assertLessEqual(max(image.size) / min(image.size), 20)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_aa_is_explicitly_deferred(self):
        for render in (get_current_endgame_card, get_next_endgame_card):
            with self.assertRaisesRegex(NotImplementedError, "deferred"):
                await render("AA")

    async def test_client_exposes_both_endgame_methods(self):
        self.assertTrue(inspect.iscoroutinefunction(HonkaiStarrail.get_current_endgame_card))
        self.assertTrue(inspect.iscoroutinefunction(HonkaiStarrail.get_next_endgame_card))
        client = HonkaiStarrail.__new__(HonkaiStarrail)
        expected = EndgameCardResult(
            game_mode="MOC", season_id=1037, season_name="Echo of Darkness", version="4.7.51",
            cards=[EndgameFloorCard(Image.new("RGBA", (10, 10)), floor=11)],
        )
        with patch("hsr_cards.renderer.nanoka.get_current_endgame_card", AsyncMock(return_value=expected)) as render:
            result = await client.get_current_endgame_card("MOC", 12, force_refresh=True)
        self.assertIs(result, expected)
        self.assertEqual(render.await_args.args[:2], ("MOC", 12))
        self.assertTrue(render.await_args.kwargs["force_refresh"])


if __name__ == "__main__":
    unittest.main()
