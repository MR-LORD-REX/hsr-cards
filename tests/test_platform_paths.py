"""CDN icon names use the same basename on Windows and POSIX hosts."""
import asyncio
import json
from pathlib import PurePosixPath
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from hsr_cards.providers.nanoka import assets as nanoka_assets
from hsr_cards.providers.nanoka.cache import specs
from hsr_cards.providers.prydwen import assets as prydwen_assets
from hsr_cards.renderer.nanoka.skills import assets as skill_assets


@pytest.mark.parametrize("loader", ["eidolon_icon", "previous_eidolon_icon"])
def test_eidolon_icons_accept_windows_sprite_paths(loader, tmp_path, monkeypatch):
    Image.new("RGBA", (24, 24), (10, 20, 30, 255)).save(
        tmp_path / "SkillIcon_1511_Ultra.webp", format="PNG",
    )
    ranks = [SimpleNamespace(key=key, rank=SimpleNamespace(
        icon=r"SpriteOutput\Avatar\SkillIcon_1511_Ultra.png",
    )) for key in (1, 2)]
    data = SimpleNamespace(
        character_id=1511, skill_icon_dir=tmp_path, rank_icon_dir=None, eidolons=ranks,
    )
    monkeypatch.setattr(skill_assets, "Path", PurePosixPath)
    image = getattr(skill_assets, loader)(data, ranks[1], 16)
    assert image is not None
    assert image.size == (16, 16)
    assert image.getpixel((0, 0)) == (10, 20, 30, 255)


def test_cached_catalog_aliases_normalize_windows_paths(tmp_path, monkeypatch):
    (tmp_path / "relicset.json").write_text(json.dumps({
        "71001": {"icon": r"SpriteOutput\ItemIcons\Relic_71001.png"},
    }), encoding="utf-8")
    (tmp_path / "monster.json").write_text(json.dumps({
        "3010101": {"icon": r"SpriteOutput\MonsterFigure\Monster_3010101.png"},
    }), encoding="utf-8")
    monkeypatch.setattr(specs, "Path", PurePosixPath)
    aliases = specs.collect_asset_specs(tmp_path)
    assert aliases["relic:71001"] == "itemfigures/Relic_71001.webp"
    assert aliases["monster:3010101"] == "monstermiddleicon/Monster_3010101.webp"


def test_prydwen_relic_and_item_references_normalize_windows_paths(tmp_path, monkeypatch):
    index = prydwen_assets.NanokaIndex(cache_dir=tmp_path, version="test")
    monkeypatch.setattr(prydwen_assets, "Path", PurePosixPath)
    relic = index.relic_asset({"id": 71001, "icon": r"SpriteOutput\ItemIcons\Relic_71001.png"})
    item = index.item_asset({"id": 1, "item_figure_icon_path": r"SpriteOutput\ItemIcons\Item_1.png"})
    assert relic.relative_path == "itemfigures/Relic_71001.webp"
    assert relic.local_name == "Relic_71001.webp"
    assert item.relative_path == "itemfigures/Item_1.webp"
    assert item.local_name == "Item_1.webp"


def test_character_asset_queries_normalize_rank_and_trace_icons(monkeypatch):
    client = nanoka_assets.AssetsQueries()
    client.get_character_detail = AsyncMock(return_value=SimpleNamespace(
        element="Ice", path_codename="knight", skills={},
        eidolons=[SimpleNamespace(id=1, icon=r"SpriteOutput\Avatar\SkillIcon_1511_Rank1.png")],
        traces=[SimpleNamespace(point=101, icon=r"SpriteOutput\Avatar\SkillIcon_1511_SkillTree1.png")],
    ))
    client.download_asset = AsyncMock(return_value=None)
    monkeypatch.setattr(nanoka_assets, "Path", PurePosixPath)
    asyncio.run(client.character_assets(1511, include_skills=False))
    client.download_asset.assert_any_await("stem:SkillIcon_1511_Rank1", refresh=False)
    client.download_asset.assert_any_await("stem:SkillIcon_1511_SkillTree1", refresh=False)


@pytest.mark.parametrize("value, expected", [
    (r"C:\SpriteOutput\Avatar2\SkillIcon_11411.png", "SkillIcon_11411"),
    ("SpriteOutput/Avatar2/SkillIcon_11411.png", "SkillIcon_11411"),
    ("SkillIcon_11411.png", "SkillIcon_11411"),
    (None, ""),
])
def test_asset_stems_are_independent_of_host_path_rules(value, expected):
    from hsr_cards.core.paths import asset_stem
    assert asset_stem(value) == expected
