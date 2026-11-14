"""Approval must refer to the exact snapshot the reviewer saw."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

import hsr_cards.prydwen.builds.registry as registry
from hsr_cards.prydwen.builds.models import BuildCardData, CharacterIdentity, ReviewStatus, SourceMeta
from hsr_cards.prydwen.builds.nanoka import NanokaIndex


@pytest.fixture
def approval_case(tmp_path, monkeypatch):
    # Structural/asset checks are tested separately; isolate source provenance.
    monkeypatch.setattr(registry, "validate_build", lambda data, nanoka: [])
    raw_dir = tmp_path / "raw"
    data_dir = tmp_path / "data"
    raw_dir.mkdir()
    data_dir.mkdir()
    raw = raw_dir / "acheron.html"
    raw.write_text("<html>reviewed build</html>\n", "utf-8")
    data = BuildCardData(
        generated_at=datetime.now(timezone.utc),
        source="https://www.prydwen.gg/star-rail/characters/acheron",
        source_meta=SourceMeta(
            url="https://www.prydwen.gg/star-rail/characters/acheron",
            raw_file=raw.name,
            html_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        ),
        character=CharacterIdentity(
            name="Acheron", slug="acheron", rarity=5, element="Lightning", path="Nihility",
            source_url="https://www.prydwen.gg/star-rail/characters/acheron",
        ),
    )
    path = registry.write_build(data, data_dir / "acheron.json")
    return path, raw, data, NanokaIndex(cache_dir=tmp_path / "catalog")


def test_changed_cached_source_blocks_approval_and_leaves_draft(approval_case):
    path, raw, _, nanoka = approval_case
    raw.write_text("<html>different recommendations</html>", "utf-8")
    with pytest.raises(ValueError, match="changed; reparse and review"):
        registry.approve_build(path, reviewer="human reviewer", nanoka=nanoka)
    assert registry.load_build(path).review.status == ReviewStatus.DRAFT


def test_matching_cached_source_can_be_explicitly_approved(approval_case):
    path, _, _, nanoka = approval_case
    result = registry.approve_build(path, reviewer="human reviewer", nanoka=nanoka)
    assert result.review.status == ReviewStatus.APPROVED
    assert result.review.reviewer == "human reviewer"


@pytest.mark.parametrize("raw_file", ["../outside.html", "..\\outside.html", "C:\\outside.html", "C:outside.html", "/outside.html", "sub/acheron.html"])
def test_raw_file_cannot_escape_adjacent_raw_directory(approval_case, raw_file):
    path, _, data, nanoka = approval_case
    data.source_meta.raw_file = raw_file
    registry.write_build(data, path)
    with pytest.raises(ValueError, match="plain filename"):
        registry.approve_build(path, reviewer="human reviewer", nanoka=nanoka)


def test_explicit_missing_snapshot_blocks_approval(approval_case):
    path, _, data, nanoka = approval_case
    data.source_meta.raw_file = "missing.html"
    registry.write_build(data, path)
    with pytest.raises(ValueError, match="snapshot is missing"):
        registry.approve_build(path, reviewer="human reviewer", nanoka=nanoka)


def test_synthetic_data_without_explicit_raw_file_needs_no_cache(approval_case):
    path, _, data, nanoka = approval_case
    data.source_meta.raw_file = None
    registry.write_build(data, path)
    assert registry.approve_build(path, reviewer="human reviewer", nanoka=nanoka).review.status == ReviewStatus.APPROVED