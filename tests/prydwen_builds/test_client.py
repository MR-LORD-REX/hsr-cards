"""Public pipeline, publication, and CLI contracts, using local files only."""
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from hsr_cards import PrydwenClient
from hsr_cards.builds import scan_builds
from hsr_cards.prydwen.builds.models import BuildCardData, CharacterIdentity, SourceMeta, ReviewStatus
from hsr_cards.prydwen.builds.registry import load_build, write_build


class EmptyAssets:
    def asset_file(self, ref):
        return None

    def stat_asset(self, *args):
        return None

    def skill_asset(self, *args):
        return None


def build(client, slug="acheron"):
    client.raw_dir.mkdir(parents=True, exist_ok=True)
    raw = client.raw_dir / f"{slug}.html"
    raw.write_bytes(b"<html>cached source</html>")
    data = BuildCardData(
        generated_at=datetime.now(timezone.utc),
        source=f"https://www.prydwen.gg/star-rail/characters/{slug}",
        source_meta=SourceMeta(url=f"https://www.prydwen.gg/star-rail/characters/{slug}",
                               raw_file=raw.name, html_sha256=hashlib.sha256(raw.read_bytes()).hexdigest()),
        character=CharacterIdentity(name=slug.title(), slug=slug, nanoka_id=1308,
                                    element="Lightning", path="Nihility",
                                    source_url=f"https://www.prydwen.gg/star-rail/characters/{slug}"),
        notes=["A source condition retained on detailed pages."],
    )
    return write_build(data, client.data_dir / f"{slug}.json")


@pytest.fixture
def client(tmp_path):
    instance = PrydwenClient(work_dir=tmp_path / ".hsr_prydwen", build_dir=tmp_path / "char_builds")
    instance.nanoka = EmptyAssets()
    return instance


def test_batch_approval_reports_failures_without_changing_invalid_drafts(client, monkeypatch):
    import hsr_cards.prydwen.builds.registry as registry
    monkeypatch.setattr(registry, "validate_build", lambda data, _: ["blocked"] if data.character.slug == "blocked" else [])
    good = build(client)
    bad = build(client, "blocked")
    result = client.approve_all(reviewer="reviewer", note="Batch checked")
    assert [data.character.slug for data in result["approved"]] == ["acheron"]
    assert len(result["failed"]) == 1
    assert "blocked" in result["failed"][0]["error"]
    assert load_build(good).review.status == ReviewStatus.APPROVED
    assert load_build(good).review.reviewer == "reviewer"
    assert load_build(bad).review.status == ReviewStatus.DRAFT


def test_drafts_stay_in_workdir_and_both_approved_variants_publish(client, monkeypatch):
    import hsr_cards.prydwen.builds.registry as registry
    import hsr_cards.prydwen.builds.client as api
    monkeypatch.setattr(registry, "validate_build", lambda *_: [])
    monkeypatch.setattr(api, "validate_build", lambda *_: [])
    source = build(client)
    preview = client.card("acheron", allow_draft=True)
    assert preview.parent == client.cards_dir
    assert not client.build_dir.exists()
    client.approve("acheron", reviewer="reviewer")
    base = client.card("acheron")
    detailed = client.card("acheron", exclude_extra=False)
    assert base == client.build_dir / "acheron" / "acheron.png"
    assert detailed == client.build_dir / "acheron" / "acheron.detailed.png"
    assert base.is_file() and detailed.is_file()
    metadata = json.loads((base.parent / "metadata.json").read_text("utf-8"))
    assert metadata["character_id"] == 1308
    assert metadata["review"]["reviewer"] == "reviewer"
    assert [item["filename"] for item in metadata["images"]] == [
        "acheron.png", "acheron.detailed.png", "acheron.detailed.conditions-01.png",
    ]
    for item in metadata["images"]:
        assert item["raw_url"].endswith("/acheron/" + item["filename"])
        assert item["git_url"].endswith("/acheron/" + item["filename"])
        assert hashlib.sha256((base.parent / item["filename"]).read_bytes()).hexdigest() == item["sha256"]
    assert not list(client.build_dir.rglob("*.render.json"))
    assert not list(client.build_dir.rglob("*manifest*"))
    assert list((client.work_dir / "reports").glob("*.render.json"))
    assert len(scan_builds(client.build_dir)) == 3
    # A changed source cannot retain an obsolete variant or obsolete pages.
    data = load_build(source)
    data.source_meta.html_sha256 = "c" * 64
    write_build(data, source)
    client.card("acheron")
    assert [record.path.name for record in scan_builds(client.build_dir)] == ["acheron.png"]
    assert not detailed.exists()


def test_batch_approved_output_and_review_files_are_separate(client, monkeypatch):
    import hsr_cards.prydwen.builds.registry as registry
    import hsr_cards.prydwen.builds.client as api
    import hsr_cards.prydwen.builds.batch as batch
    for module in (registry, api, batch):
        monkeypatch.setattr(module, "validate_build", lambda *_: [])
    build(client)
    client.approve("acheron")
    result = client.cards(exclude_extra=False)
    assert not result["failed"]
    assert Path(result["cards"][0]["image"]).parent == client.build_dir / "acheron"
    assert (client.cards_dir / "review-manifest.json").is_file()
    assert (client.cards_dir / result["contact_sheets"][0]).is_file()
    assert len(scan_builds(client.build_dir)) == 2


def test_default_workdir_finds_root_from_nested_cwd(tmp_path, monkeypatch):
    root = tmp_path / ".hsr_prydwen"
    root.mkdir()
    nested = tmp_path / "repo" / "src"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert PrydwenClient().work_dir == root


@pytest.mark.parametrize("command", [
    ["card", "acheron", "--detailed"],
    ["card", "acheron", "--no-exclude-extra"],
    ["card", "acheron"],
    ["approve-all", "acheron", "--reviewer", "test"],
    ["approve", "--all", "--reviewer", "test"],
])
def test_cli_delegates_variant_and_batch_arguments(command, monkeypatch):
    from hsr_cards.prydwen.builds import cli
    instance = Mock()
    instance.approve_all.return_value = {"approved": [], "failed": []}
    monkeypatch.setattr(cli, "PrydwenClient", Mock(return_value=instance))
    cli.main(command)
    if command[0] == "card":
        assert instance.card.call_args.kwargs["exclude_extra"] == (len(command) == 2)
    else:
        assert instance.approve_all.call_args.kwargs["reviewer"] == "test"
