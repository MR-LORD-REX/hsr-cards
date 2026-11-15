"""Offline contracts for lazy imports, renderer boundaries, and service ownership."""
import asyncio
import importlib
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import get_args, get_type_hints
from unittest.mock import AsyncMock, patch

from PIL import Image
import pytest

from hsr_cards import HonkaiStarrail, get_current_endgame_card, get_next_endgame_card
from hsr_cards.providers.nanoka.models import MazeSchedule
from hsr_cards.providers.hoyolab.api import BaseAPI
from hsr_cards.services import character_data, characters
from hsr_cards.services.endgame import api


def test_all_public_exports_are_silent_and_offline_in_a_fresh_process():
    code = '''
from pathlib import Path
from unittest.mock import patch
import sys
with patch.object(Path, "mkdir", side_effect=AssertionError("import created a directory")), \\
     patch.object(Path, "cwd", side_effect=AssertionError("import discovered a path")):
    import hsr_cards
    assert "hsr_cards.providers.prydwen" not in sys.modules
    for name in hsr_cards.__all__:
        getattr(hsr_cards, name)
    facade = hsr_cards.HonkaiStarrail()
    assert facade._hoyolab is facade._nanoka is facade._prydwen is None
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    with TemporaryDirectory() as directory:
        result = subprocess.run([sys.executable, "-c", code], cwd=directory, env=env,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        assert list(Path(directory).iterdir()) == []


def test_direct_service_imports_have_no_circular_dependency():
    code = '''
from hsr_cards.services.skills import build_skill_data
from hsr_cards.services.character_info import build_card_data
from hsr_cards.services.endgame.api import get_current_endgame_card
from hsr_cards.renderer.nanoka import get_character_info
from hsr_cards import *
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("working_directory", ["project", "elsewhere"])
def test_standalone_launcher_imports_without_pythonpath(tmp_path, working_directory):
    project = Path(__file__).resolve().parents[1]
    code = '''
import asyncio
import importlib
import runpy
import sys
from unittest.mock import patch

def skip_card_requests(coroutine):
    coroutine.close()

with patch("dotenv.load_dotenv", return_value=False), \\
     patch("os.makedirs"), \\
     patch.object(asyncio, "run", side_effect=skip_card_requests) as run:
    namespace = runpy.run_path(sys.argv[1], run_name="__main__")
    run.assert_called_once()

from hsr_cards import HonkaiStarrail, NanokaClient, PrydwenClient
from hsr_cards.models.auth import Cookies
assert namespace["HonkaiStarrail"] is HonkaiStarrail
assert namespace["NanokaClient"] is NanokaClient
assert namespace["PrydwenClient"] is PrydwenClient
assert namespace["Cookies"] is Cookies
assert not any(name.startswith("src.hsr_cards") for name in sys.modules)
assert importlib.import_module("hsr_cards.prydwen.builds.models") is importlib.import_module("hsr_cards.providers.prydwen.models")
'''
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    cwd = project if working_directory == "project" else tmp_path
    result = subprocess.run([sys.executable, "-I", "-c", code, str(project / "main.py")],
                            cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_historical_imports_resolve_the_same_objects():
    assert importlib.import_module("hsr_cards.renderer.nanoka.endgames") is api
    assert importlib.import_module("hsr_cards.renderer.nanoka.data") is character_data
    from hsr_cards.renderer.nanoka.character_skills import SkillData, render_full
    from hsr_cards.renderer.nanoka.skills.models import SkillData as CanonicalSkillData
    from hsr_cards.renderer.nanoka.skills.rendering import render_full as canonical_render
    from hsr_cards.renderer.nanoka.character_variants import build_card_data
    from hsr_cards.services.character_info import build_card_data as canonical_build
    assert SkillData is CanonicalSkillData
    assert render_full is canonical_render
    assert build_card_data is canonical_build


def test_endgame_editor_suggestions_include_all_modes_on_both_entry_points():
    for function in (get_current_endgame_card, get_next_endgame_card,
                     HonkaiStarrail.get_current_endgame_card, HonkaiStarrail.get_next_endgame_card):
        assert get_args(get_type_hints(function)["game_mode"]) == ("MOC", "PF", "AS", "AA")


def provider(language="en"):
    current = MazeSchedule(id=10, live_begin="2020-01-01", live_end="2090-01-01")
    later = MazeSchedule(id=11, live_begin="2090-01-01", live_end="2091-01-01")
    undated = MazeSchedule(id=12)
    return SimpleNamespace(
        version="test-build", language=language, initialize=AsyncMock(), close=AsyncMock(),
        cache=SimpleNamespace(load_json=AsyncMock(return_value=[]), asset_file=lambda name: Path("missing") / name),
        get_current_endgame=AsyncMock(return_value=SimpleNamespace(schedule=current)),
        list_maze=AsyncMock(return_value=[undated, later, current]),
        get_endgame_payload=AsyncMock(return_value=[{"id": 1, "name": "Reference (I)"}]),
        fetch_asset=AsyncMock(return_value=None),
    )


def test_current_creates_one_client_and_closes_it_after_rendering():
    client = provider()
    with patch.object(api, "NanokaClient", return_value=client) as factory, \
         patch.object(api, "render_floor_card", return_value=Image.new("RGBA", (10, 10))):
        result = asyncio.run(get_current_endgame_card("PF", 1, use_rendered_cache=False))
    factory.assert_called_once()
    client.initialize.assert_awaited_once()
    client.close.assert_awaited_once()
    assert result.season_id == 10
    client.get_endgame_payload.assert_awaited_once_with(10, mode="maze_extra")


def test_next_reuses_one_owned_client_for_multiple_seasons():
    client = provider()
    with patch.object(api, "NanokaClient", return_value=client) as factory, \
         patch.object(api, "render_floor_card", return_value=Image.new("RGBA", (10, 10))):
        results = asyncio.run(get_next_endgame_card("AS", 1, look_ahead="max", use_rendered_cache=False))
    factory.assert_called_once()
    client.initialize.assert_awaited_once()
    client.close.assert_awaited_once()
    assert [result.season_id for result in results] == [11, 12]
    assert client.get_endgame_payload.await_count == 2
    assert results[-1].begins_at is results[-1].ends_at is None


def test_borrowed_client_remains_open_and_uses_its_locale_for_render_cache(tmp_path):
    client = provider(language="zh")
    with patch.object(api, "NanokaClient", side_effect=AssertionError("must reuse injected client")), \
         patch.object(api, "render_floor_card", return_value=Image.new("RGBA", (10, 10))):
        result = asyncio.run(get_current_endgame_card("PF", 1, client=client, rendered_cache_dir=tmp_path))
    client.initialize.assert_not_awaited()
    client.close.assert_not_awaited()
    assert result.cards[0].cache_path.name.endswith("_zh.png")


def test_owned_client_closes_if_initialization_fails():
    client = provider()
    client.initialize.side_effect = RuntimeError("offline")
    with patch.object(api, "NanokaClient", return_value=client), pytest.raises(RuntimeError, match="offline"):
        asyncio.run(get_current_endgame_card("PF", 1))
    client.close.assert_awaited_once()


def test_borrowed_client_is_not_closed_on_failure():
    client = provider()
    client.get_current_endgame.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError, match="offline"):
        asyncio.run(get_current_endgame_card("PF", 1, client=client))
    client.close.assert_not_awaited()


def test_comparison_failure_closes_the_first_character_client():
    before = SimpleNamespace(client=SimpleNamespace(close=AsyncMock()))
    with patch.object(character_data, "load_character", AsyncMock(side_effect=[before, RuntimeError("missing build")])), \
         pytest.raises(RuntimeError, match="missing build"):
        asyncio.run(character_data.load_pair(1507, "first", "second"))
    before.client.close.assert_awaited_once()


def test_catalog_failure_closes_the_owned_character_client():
    client = provider()
    client.cache.load_json.side_effect = RuntimeError("bad catalog")
    summary = SimpleNamespace(id=1507)
    with patch.object(character_data, "NanokaClient", return_value=client), \
         patch.object(character_data, "_resolve_character", AsyncMock(return_value=(summary, object()))), \
         pytest.raises(RuntimeError, match="bad catalog"):
        asyncio.run(character_data.load_character(1507))
    client.close.assert_awaited_once()


def test_batch_records_individual_errors_and_preserves_input_order():
    async def render(identifier, *args, **kwargs):
        if identifier == 2:
            raise RuntimeError("one failed")
        return SimpleNamespace(image=Image.new("RGBA", (10, 10)))
    with patch("hsr_cards.renderer.nanoka.get_character_info", render):
        result = asyncio.run(characters.render_all_info(identifiers=[1, 2, 3, 1], use_rendered_cache=False))
    assert [item.identifier for item in result.items] == [1, 2, 3]
    assert [item.identifier for item in result.succeeded] == [1, 3]
    assert str(result.errors[2]) == "one failed"


def test_batch_cancellation_propagates_to_the_caller():
    with patch("hsr_cards.renderer.nanoka.get_character_info", AsyncMock(side_effect=asyncio.CancelledError)), \
         pytest.raises(asyncio.CancelledError):
        asyncio.run(characters.render_all_info(identifiers=[1], use_rendered_cache=False))


def test_hoyolab_session_replacement_preserves_owned_cleanup_and_borrowed_ownership():
    owned = SimpleNamespace(closed=False, close=AsyncMock())
    borrowed = SimpleNamespace(closed=False, close=AsyncMock())
    async def check():
        with patch("hsr_cards.providers.hoyolab.api.aiohttp.ClientSession", return_value=owned):
            api = BaseAPI("800000000")
            assert api.session is owned
        api.session = owned
        assert api._owns_session
        with pytest.raises(RuntimeError, match="Close the owned"):
            api.session = borrowed
        assert api.session is owned
        await api.close()
        owned.close.assert_awaited_once()
        api.session = borrowed
        assert api.session is borrowed
        await api.close()
        borrowed.close.assert_not_awaited()
    asyncio.run(check())
