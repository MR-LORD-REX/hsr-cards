"""Character-build selection and remote updates for multi-image metadata."""
import asyncio
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from PIL import Image

from hsr_cards.builds import (
    build_raw_url, build_tree_url, find_builds, scan_builds, update_build_assets,
)
from hsr_cards.nanoka import NanokaClient
from hsr_cards.utils.errors import HSR_Error


def metadata():
    names = ["acheron.png", "acheron.detailed.png", "acheron.detailed.conditions-01.png", "acheron.detailed.conditions-02.png"]
    return {
        "character_id": 1308, "char_name": "Acheron", "slug": "acheron",
        "images": [dict(filename=name, detailed=index > 0,
                        raw_url=build_raw_url("acheron", name),
                        git_url=build_tree_url("acheron", name)) for index, name in enumerate(names)],
    }


def save_assets(root, payload=None):
    payload = payload or metadata()
    folder = root / payload["slug"]
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")
    for index, item in enumerate(payload["images"]):
        Image.new("RGB", (10, 10), (index, 0, 0)).save(folder / item["filename"])
    return payload


def test_nanoka_returns_single_clean_or_ordered_detailed_images_and_links(tmp_path):
    payload = save_assets(tmp_path)
    async def run():
        client = NanokaClient(include_assets=False)
        client.get_character = AsyncMock(side_effect=AssertionError("local lookup must be offline"))
        image = await client.character_build("Acheron", build_dir=tmp_path)
        assert isinstance(image, Image.Image)
        assert image.getpixel((0, 0)) == (0, 0, 0)
        assert await client.character_build(1308, url=True, build_dir=tmp_path) == payload["images"][0]["raw_url"]
        images = await client.character_build("acheron", detailed=True, build_dir=tmp_path)
        assert [image.getpixel((0, 0)) for image in images] == [(1, 0, 0), (2, 0, 0), (3, 0, 0)]
        links = await client.character_build(1308, detailed=True, url=True, build_dir=tmp_path)
        assert links == [item["raw_url"] for item in payload["images"][1:]]
        client.get_character.assert_not_awaited()
    asyncio.run(run())


def test_filters_use_nanoka_resolution_and_missing_images_do_not_return_partial_lists(tmp_path):
    save_assets(tmp_path)
    async def run():
        client = NanokaClient(include_assets=False)
        client.get_character = AsyncMock(return_value=SimpleNamespace(summary=SimpleNamespace(id=1308)))
        links = await client.character_build(element="lightning", detailed=True, url=True, build_dir=tmp_path)
        assert len(links) == 3
        assert client.get_character.call_args.kwargs["element"] == "lightning"
        (tmp_path / "acheron" / "acheron.detailed.conditions-02.png").unlink()
        assert await client.character_build(1308, detailed=True, build_dir=tmp_path) is None
    asyncio.run(run())


class Response:
    def __init__(self, *, payload=None, data=b"", status=200):
        self.payload, self.data, self.status = payload, data, status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self, **kwargs):
        return self.payload

    async def read(self):
        return self.data


def session(payload, *, fail=False):
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, "PNG")
    def get(url, **kwargs):
        if url == "https://example.test/metadata.json":
            return Response(payload=payload)
        return Response(data=buffer.getvalue(), status=503 if fail else 200)
    return SimpleNamespace(get=Mock(side_effect=get))


def test_remote_update_downloads_all_variants_and_writes_both_metadata_indexes(tmp_path):
    data = metadata()
    local = save_assets(tmp_path, {**data, "slug": "local-only", "character_id": 9999})
    (tmp_path / "metadata.json").write_text(json.dumps({"9999": local}), encoding="utf-8")
    transport = session({"1308": data})
    count = asyncio.run(update_build_assets(transport, metadata_url="https://example.test/metadata.json", build_dir=tmp_path))
    assert count == 4
    assert transport.get.call_count == 5
    assert len(scan_builds(tmp_path)) == 8
    assert len(find_builds(1308, detailed=True, build_dir=tmp_path)) == 3
    assert json.loads((tmp_path / "acheron" / "metadata.json").read_text("utf-8")) == data
    assert set(json.loads((tmp_path / "metadata.json").read_text("utf-8"))) == {"1308", "9999"}


def test_failed_remote_update_keeps_previous_metadata(tmp_path):
    old = {"9999": {"local": True}}
    (tmp_path / "metadata.json").write_text(json.dumps(old), encoding="utf-8")
    with pytest.raises(HSR_Error, match="Failed to update"):
        asyncio.run(update_build_assets(session({"1308": metadata()}, fail=True),
                                        metadata_url="https://example.test/metadata.json", build_dir=tmp_path))
    assert json.loads((tmp_path / "metadata.json").read_text("utf-8")) == old
    assert not (tmp_path / "acheron" / "metadata.json").exists()


@pytest.mark.parametrize("field,value", [("slug", "../outside"), ("filename", "../outside.png"), ("filename", "C:outside.png")])
def test_remote_metadata_paths_stay_inside_character_directory(tmp_path, field, value):
    data = metadata()
    if field == "slug":
        data[field] = value
    else:
        data["images"][0][field] = value
    with pytest.raises(HSR_Error, match="plain filename"):
        asyncio.run(update_build_assets(session({"1308": data}), metadata_url="https://example.test/metadata.json", build_dir=tmp_path))
    assert not list(tmp_path.rglob("*.png"))


def test_main_client_returns_the_same_single_and_detailed_variants(tmp_path):
    with patch("dotenv.load_dotenv"), patch.dict("os.environ", {
        "ltoken_v2": "test-token", "ltuid_v2": "123456", "default_uid": "800556377",
    }):
        from hsr_cards import HonkaiStarrail
    save_assets(tmp_path)
    async def run():
        client = HonkaiStarrail.__new__(HonkaiStarrail)
        assert isinstance(await client.character_build("Acheron", build_dir=tmp_path), Image.Image)
        links = await client.character_build("Acheron", url=True, detailed=True, build_dir=tmp_path)
        assert links[0].endswith("/acheron/acheron.detailed.png")
        assert len(links) == 3
        images = await client.character_build(1308, detailed=True, build_dir=tmp_path)
        assert len(images) == 3 and all(isinstance(image, Image.Image) for image in images)
    asyncio.run(run())


def test_missing_variant_for_a_known_character_returns_none_without_network(tmp_path):
    payload = metadata()
    payload["images"] = payload["images"][:1]
    save_assets(tmp_path, payload)
    async def run():
        client = NanokaClient(include_assets=False)
        client.get_character = AsyncMock(side_effect=AssertionError("must stay offline"))
        assert await client.character_build(1308, detailed=True, build_dir=tmp_path) is None
        client.get_character.assert_not_awaited()
    asyncio.run(run())
