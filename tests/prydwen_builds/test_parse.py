"""Offline regressions for source fidelity, not renderer implementation details."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hsr_cards.prydwen.builds.models import ReviewStatus, WeightClass
from hsr_cards.prydwen.builds.nanoka import NanokaIndex
from hsr_cards.prydwen.builds.parse import parse_html
from hsr_cards.prydwen.builds.registry import validate_build

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def nanoka(tmp_path):
    index = NanokaIndex(cache_dir=tmp_path / "catalog")
    names = {
        1308: ("Acheron", "acheron"), 1507: ("Mortenax Blade", "mortenax-blade"),
        1403: ("Tribbie", "tribbie"), 1409: ("Hyacine", "hyacine"),
        1217: ("Huohuo", "huohuo"), 1303: ("Ruan Mei", "ruan-mei"),
        1504: ("Ashveil", "ashveil"), 1401: ("The Herta", "the-herta"),
        1415: ("Cyrene", "cyrene"), 1111: ("Luka", "luka"),
    }
    index.characters = {identifier: {"id": identifier, "en": name, "icon": slug} for identifier, (name, slug) in names.items()}
    index._character_by_name = index._name_map(index.characters)
    return index


def parse_fixture(slug, nanoka, *, raw_path=None):
    html = (FIXTURES / f"{slug}-build.html").read_text("utf-8")
    return parse_html(html, source_url=f"https://www.prydwen.gg/star-rail/characters/{slug}", nanoka=nanoka, raw_path=raw_path)


def test_source_updates_and_snapshot_hash_are_separate_from_fetch_time(nanoka, tmp_path):
    html = (FIXTURES / "acheron-build.html").read_text("utf-8")
    raw = tmp_path / "acheron.html"
    raw.write_text(html, "utf-8")
    raw.with_suffix(".meta.json").write_text(json.dumps({"fetched_at": "2026-11-14T01:02:03+00:00"}), "utf-8")
    data = parse_fixture("acheron", nanoka, raw_path=raw)
    assert data.character.last_updated == "11/November/2026"
    assert data.source_meta.last_review_update == "Patch 4.7"
    assert data.source_meta.last_major_build_update == "Patch 4.7"
    assert data.source_meta.website_updates["updatedAt"] == "2026-11-11T03:53:46.731Z"
    assert data.source_meta.fetched_at.isoformat() == "2026-11-14T01:02:03+00:00"
    assert data.source_meta.html_sha256 == hashlib.sha256(html.encode("utf-8")).hexdigest()
    assert data == parse_fixture("acheron", nanoka, raw_path=raw)
    assert data.review.status == ReviewStatus.DRAFT


def test_trace_operators_and_specialist_restriction_survive(nanoka):
    data = parse_fixture("the-herta", nanoka)
    assert [step.label for step in data.trace_priority.skill_steps] == ["Talent", "Skill", "Ultimate", "Basic"]
    assert data.trace_priority.skill_operators == [">=", "=", ">"]
    specialist = next(group for group in data.relic_sets if "Specialist" in group.heading)
    assert specialist.weight == WeightClass.SPECIALIST
    assert "<95 Speed" in specialist.recommendations[0].reason
    assert data.main_stats[3].operators == [">="]


def test_two_piece_combination_remains_one_recommendation_group(nanoka):
    data = parse_fixture("luka", nanoka)
    pairs = [row for group in data.relic_sets for row in group.recommendations if row.combination_id]
    assert [row.name for row in pairs] == ["Prisoner in Deep Confinement", "Pioneer Diver of Dead Waters"]
    assert pairs[0].combination_id == pairs[1].combination_id
    assert all(row.pieces == 2 and row.slot == "cavern" for row in pairs)
    assert pairs[0].rank == pairs[1].rank == 4


def test_editorial_slot_alternatives_are_not_five_member_team(nanoka):
    data = parse_fixture("acheron", nanoka)
    team = data.editorial_teams[0]
    assert len(team.slots) == 4
    assert [len(slot.members) for slot in team.slots] == [1, 1, 1, 2]
    assert all(member.slot == 3 for member in team.slots[3].members)
    assert team.slots[3].role == "Sustain"


def test_all_modes_come_from_distinct_embedded_analytics(nanoka):
    data = parse_fixture("acheron", nanoka)
    assert [mode.mode for mode in data.teams] == ["moc", "pf", "as", "anomaly"]
    assert [mode.variants[0].rank for mode in data.teams] == [35, 14, 33, 65]
    assert data.teams[0].variants[0].raw_metrics["avg_round"] == 12
    assert data.teams[1].variants[0].raw_metrics["avg_round"] == 34810
    assert data.teams[0].variants[1].raw_metrics["avg_round"] == 99.99
    assert data.teams[0].variants[1].performance["Avg. cycles"] == "-"
    assert all(mode.phase and mode.source_path for mode in data.teams)


def test_dom_fallback_does_not_copy_one_mode_to_three_others(nanoka):
    data = parse_fixture("cyrene", nanoka)
    assert len(data.teams[0].variants) > 0
    assert all(not mode.variants for mode in data.teams[1:])


def test_wrong_mode_snapshot_filename_does_not_relabel_teams(nanoka, tmp_path):
    html = (FIXTURES / "cyrene-build.html").read_text("utf-8")
    raw = tmp_path / "cyrene.html"
    raw.write_text(html, "utf-8")
    (tmp_path / "cyrene.1.html").write_text(html, "utf-8")
    data = parse_fixture("cyrene", nanoka, raw_path=raw)
    assert not data.teams[1].variants


def test_unresolved_character_keeps_its_asset_position(nanoka):
    data = parse_fixture("acheron", nanoka)
    team = data.teams[0].variants[0]
    assert team.characters == ["Acheron", "Mortenax Blade", "Tribbie", "Hyacine"]
    assert len(team.character_assets) == len(team.characters)
    # An unresolved ally must leave a null, never shift every later portrait.
    nanoka.characters.pop(1507)
    nanoka._character_by_name = nanoka._name_map(nanoka.characters)
    team = parse_fixture("acheron", nanoka).teams[0].variants[0]
    assert team.character_assets[1] is None
    assert team.character_assets[2].ref == "character:1403"


def test_no_build_page_stays_empty_with_explicit_diagnostics(nanoka):
    data = parse_html("<html><h1>New Character</h1></html>", source_url="https://www.prydwen.gg/star-rail/characters/new", nanoka=nanoka)
    assert not data.light_cones and not data.relic_sets and not data.main_stats and not data.teams
    assert data.character.rarity is None
    assert not data.diagnostics["has_build_section"]
    assert "Build and teams section not found in the saved HTML" in data.warnings
    assert data.review.status == ReviewStatus.DRAFT


def test_profile_eidolons_never_become_an_investment_order(nanoka):
    html = (FIXTURES / "cyrene-build.html").read_text("utf-8")
    html += '<div class="content-header">Eidolons</div><div><div class="box"><div class="skill-icon">E1</div><div class="skill-name">Kit inventory</div></div></div>'
    data = parse_html(html, source_url="https://www.prydwen.gg/star-rail/characters/cyrene", nanoka=nanoka)
    assert not data.investment.order


def test_empty_mode_wrappers_cannot_pass_team_validation(nanoka):
    data = parse_fixture("acheron", nanoka)
    for mode in data.teams:
        mode.variants = []
    data.editorial_teams = []
    data.synergies = []
    assert "no teams or synergies parsed" in validate_build(data, nanoka)

def test_relic_reason_cannot_be_stolen_from_later_row(nanoka):
    data = parse_fixture("luka", nanoka)
    rows = data.relic_sets[0].recommendations
    assert rows[0].name == "Prisoner in Deep Confinement"
    assert rows[0].reason is None
    assert rows[1].name == "Thief of Shooting Meteor"
    assert rows[1].reason == "Break"
    assert rows[2].name == "Champion of Streetwise Boxing"
    assert rows[2].reason is None
    assert all(row.reason == "1 Debuff Required (Pioneer)" for row in rows[3:5])


def test_substat_greater_or_equal_remains_one_comparison(nanoka):
    data = parse_fixture("luka", nanoka)
    assert data.substats == ["SPD (breakpoint) = EHR (until cap)", "Break Effect >= ATK%"]


def test_new_badge_cannot_replace_character_image_alt(nanoka):
    html = (FIXTURES / "acheron-build.html").read_text("utf-8")
    html = html.replace('href="/star-rail/characters/acheron">', 'href="/star-rail/characters/acheron"><span class="floating-element new">New</span>')
    data = parse_html(html, source_url="https://www.prydwen.gg/star-rail/characters/acheron", nanoka=nanoka)
    assert data.editorial_teams[0].slots[0].members[0].name == "Acheron"
    assert all(member.name != "New" for team in data.editorial_teams for member in team.members)


def test_rank_one_specialist_cone_preserves_restriction(nanoka):
    data = parse_fixture("asta", nanoka)
    assert len(data.light_cones) == 4
    assert data.light_cones[0].weight == WeightClass.BEST
    special = data.light_cones[-1]
    assert special.name == "Planetary Rendezvous"
    assert special.rank == 1
    assert special.weight == WeightClass.SPECIALIST
    assert special.heading == "Specialist Light Cones"
    assert "restriction" in special.reason