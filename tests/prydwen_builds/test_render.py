"""Information-preserving render checks, without network or game assets."""
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from hsr_cards.prydwen.builds.models import (
    BuildCardData, CharacterIdentity, LightConeRecommendation,
    RelicRecommendation, RelicWeightGroup, SourceMeta, StatChoice,
    StatTarget, WeightClass,
)
from hsr_cards.prydwen.builds.render import _choice_text, _font, _relic_display, _wrap, render_card


class EmptyAssets:
    def asset_file(self, ref):
        return None

    def stat_asset(self, *args):
        return None

    def skill_asset(self, *args):
        return None


def build():
    return BuildCardData(
        generated_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
        source="https://www.prydwen.gg/star-rail/characters/example",
        source_meta=SourceMeta(
            url="https://www.prydwen.gg/star-rail/characters/example",
            last_updated="11/November/2026", html_sha256="b" * 64,
        ),
        character=CharacterIdentity(
            name="Example", slug="example", rarity=5, element="Ice",
            path="Erudition", source_url="https://www.prydwen.gg/star-rail/characters/example",
        ),
    )


def test_relic_display_keeps_two_piece_pairs_complete():
    group = RelicWeightGroup(heading="Best", weight=WeightClass.BEST)
    standalone = RelicRecommendation(name="Four", pieces=4)
    pair = [RelicRecommendation(name=name, pieces=2, combination_id="pair") for name in ("A", "B")]
    candidates = [(group, standalone), *[(group, item) for item in pair]]
    assert [r.name for _, r in _relic_display(candidates)] == ["Four", "A", "B"]
    assert [r.name for _, r in _relic_display(candidates, limit=2)] == ["Four"]
    assert _relic_display([(group, pair[0])]) == []


def test_stat_choice_preserves_source_comparison_operators():
    choice = StatChoice(slot="Body", values=["CRIT Rate", "CRIT DMG", "ATK%"],
                        operators=[">=", "="], raw_text="Body CRIT Rate >= CRIT DMG = ATK%")
    assert _choice_text(choice) == "CRIT Rate >= CRIT DMG = ATK%"
    assert _choice_text(StatChoice(slot="Body", raw_text="Source unavailable")) == "Source unavailable"


def test_long_unbroken_source_tokens_do_not_escape_note_columns():
    font = _font(28, "source")
    lines = _wrap("token" * 400, font, 864)
    assert len(lines) > 1
    assert all(font.getlength(line) <= 864 for line in lines)
    assert "".join(lines) == "token" * 400


def test_offline_render_keeps_conditions_and_replaces_only_its_own_sheets(tmp_path):
    data = build()
    condition = "Only with this specific teammate and below 95 Speed. " * 90
    data.light_cones = [LightConeRecommendation(name="Conditional cone", reason=condition)]
    data.stat_targets = [StatTarget(stat="SPD", target="134 or 160", notes=["Choose based on the exact teammate and set."])]
    output = tmp_path / "example.detailed.png"
    stale = tmp_path / "example.detailed.conditions-99.png"
    stale.write_bytes(b"stale")
    unrelated = tmp_path / "another.conditions-99.png"
    unrelated.write_bytes(b"other character")
    render_card(data, output, nanoka=EmptyAssets(), exclude_extra=False)
    report = json.loads(output.with_suffix(".render.json").read_text(encoding="utf-8"))
    assert Image.open(output).size == (1920, 1440)
    assert report["review_status"] == "draft"
    assert report["source_html_sha256"] == "b" * 64
    assert report["requires_condition_sheets"]
    assert len(report["condition_sheets"]) >= 2
    assert next(note for note in report["conditions"] if note["id"] == "L1")["text"] == condition.strip()
    assert "specific teammate" in next(note for note in report["conditions"] if note["id"] == "L1")["text"]
    assert next(note for note in report["conditions"] if note["id"] == "T1")["text"].endswith("Choose based on the exact teammate and set.")
    assert not stale.exists()
    assert unrelated.read_bytes() == b"other character"
    assert set(report["outputs"]) == {output.name, *report["condition_sheets"]}
    assert all((tmp_path / name).exists() for name in report["outputs"])
    # A second render with less content must not leave old conditional advice.
    data.light_cones = []
    data.stat_targets = []
    old_count = len(report["condition_sheets"])
    render_card(data, output, nanoka=EmptyAssets(), exclude_extra=False)
    replacement = json.loads(output.with_suffix(".render.json").read_text(encoding="utf-8"))
    assert len(replacement["condition_sheets"]) < old_count
    assert len(list(tmp_path.glob("example.detailed.conditions-*.png"))) == len(replacement["condition_sheets"])

def test_conditional_trace_and_overflow_targets_remain_in_source_notes(tmp_path):
    from hsr_cards.prydwen.builds.models import Synergy, TracePriority, TraceStep
    data = build()
    data.trace_priority = TracePriority(
        skills="Ultimate > Skill (healing focus) or Talent > Basic (DPS focus)",
        skill_steps=[TraceStep(label=str(i)) for i in range(11)],
        raw_text="Ultimate > Skill (healing focus) or Talent > Basic (DPS focus)",
    )
    data.stat_targets = [StatTarget(stat="CRIT RATE", target="0% or 40-67%", notes=["Depends on gear."]) for _ in range(7)]
    data.synergies = [Synergy(characters=["Long character name one", "Long character name two", "Long character name three", "Long character name four"], character_assets=[None] * 4, note="Choose a character from this grouped source synergy.")]
    output = tmp_path / "example.detailed.png"
    render_card(data, output, nanoka=EmptyAssets(), exclude_extra=False)
    report = json.loads(output.with_suffix(".render.json").read_text(encoding="utf-8"))
    assert any(note["id"] == "T7" for note in report["conditions"])
    assert any(note["id"] == "P1" and "healing focus" in note["text"] for note in report["conditions"])
    assert any("Conditional trace priority" in item for item in report["omitted_options"])
    assert not any("40-67%" in item for item in report["clipped_text"])
    assert not any("Long character" in item for item in report["clipped_text"])

def test_clean_default_hides_references_and_overflow_without_changing_source(tmp_path, monkeypatch):
    import re
    import hsr_cards.prydwen.builds.render as renderer
    from hsr_cards.prydwen.builds.models import EditorTeam, EditorTeamSlot, EditorTeamMember, Synergy
    data = build()
    data.light_cones = [LightConeRecommendation(name=f"Cone {i}", reason="Conditional advice") for i in range(5)]
    team = EditorTeam(name="Team", slots=[EditorTeamSlot(members=[EditorTeamMember(name=f"Member {i}") for i in range(3)])])
    data.editorial_teams = [team] * 3
    data.stat_targets = [StatTarget(stat="SPD", target="134", notes=["Condition"]) for _ in range(7)]
    original = data.model_dump_json()
    painted = []
    draw_text = renderer._text
    def capture(ctx, text, *args, **kwargs):
        painted.append(text)
        return draw_text(ctx, text, *args, **kwargs)
    monkeypatch.setattr(renderer, "_text", capture)
    output = renderer.render_card(data, tmp_path / "example.png", nanoka=EmptyAssets())
    assert output.name == "example.png"
    report = json.loads(output.with_suffix(".render.json").read_text("utf-8"))
    assert report["outputs"] == ["example.png"]
    assert report["conditions"] == []
    assert not report["requires_condition_sheets"]
    assert not any(re.search(r"\[(?:[A-Z]+\d*|IDs)\]|\+\d+|in JSON|condition sheets", text) for text in painted)
    assert data.model_dump_json() == original
    # Both variants coexist and cleaning again leaves detailed pages intact.
    detailed = renderer.render_card(data, output, nanoka=EmptyAssets(), exclude_extra=False)
    assert detailed.name == "example.detailed.png"
    sheets = list(tmp_path.glob("example.detailed.conditions-*.png"))
    assert sheets
    renderer.render_card(data, output, nanoka=EmptyAssets())
    assert detailed.is_file() and all(path.is_file() for path in sheets)
