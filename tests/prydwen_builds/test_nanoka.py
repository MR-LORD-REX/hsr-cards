"""Identity and icon regressions that would put misleading art on a card."""

import json
from pathlib import Path

import pytest

from hsr_cards.prydwen.builds.nanoka import NanokaIndex


@pytest.fixture
def index(tmp_path):
    data = tmp_path / "test" / "en" / "data"
    data.mkdir(parents=True)
    characters = {
        "1001": {"en": "March 7th", "icon": "mar7th"},
        "1224": {"en": "March 7th", "icon": "mar7th2"},
        "1205": {"en": "Blade", "icon": "blade"},
        "1213": {"en": "Dan Heng • Imbibitor Lunae", "icon": "danhengil"},
        "1308": {"en": "Acheron", "icon": "acheron"},
        "1507": {"en": "Mortenax Blade", "icon": "blademortenax"},
        "8001": {"en": "{NICKNAME}", "icon": "playerboy"},
        "8003": {"en": "{NICKNAME}", "icon": "playerboy2"},
        "8007": {"en": "{NICKNAME}", "icon": "playerboy4"},
    }
    (data / "character.json").write_text(json.dumps(characters), encoding="utf-8")
    return NanokaIndex(cache_dir=tmp_path, version="test")


def test_explicit_slug_overrides_reused_display_name(index):
    assert index.character_id(name="Blade", slug="blade-mortenax") == 1507
    assert index.character_id(name="March 7th", slug="march-7th-swordmaster") == 1224
    assert index.character_id(name="March 7th", slug="march-7th") == 1001
    assert index.character_id(slug="imbibitor-lunae") == 1213


def test_ambiguous_or_unknown_forms_remain_unresolved(index):
    assert index.character_id(name="March 7th") is None
    assert index.character_id(name="Trailblazer") is None
    assert index.character_id(name="Trailblazer • Future Path") is None
    assert index.character_id(name="{NICKNAME}") is None
    assert index.character_id(name="Blade", slug="blade-future-form") is None
    assert index.character_id(name="Acheron LV.999") is None
    assert index.character_id(slug="march-7th-future-form") is None


def test_informative_alternate_form_names_are_preserved(index):
    assert index.match_character("March 7th • The Hunt") == (1224, "March 7th • The Hunt")
    assert index.match_character("Trailblazer • Remembrance") == (8007, "Trailblazer • Remembrance")


def test_stat_icons_do_not_confuse_crit_energy_or_unknown_percent(index):
    assert index.stat_asset("CRIT DMG", "Lightning").relative_path == "skillicons/IconCriticalDamage.webp"
    assert index.stat_asset("Energy Regen Rate").relative_path == "skillicons/IconEnergyRecovery.webp"
    assert index.stat_asset("Outgoing Healing Boost").relative_path == "skillicons/IconHealRatio.webp"
    assert index.stat_asset("Lightning DMG").relative_path == "element/thunder.webp"
    assert index.stat_asset("Future stat%") is None
    assert index.stat_asset("Future damage%", "Lightning") is None


def test_major_traces_use_skill_tree_not_eidolon_art(index):
    assert index.trace_asset(1308, "A2 Major trace").relative_path.endswith("SkillTree1.webp")
    assert index.trace_asset(1308, "A4 Major trace").relative_path.endswith("SkillTree2.webp")
    assert index.trace_asset(1308, "A6 Major trace").relative_path.endswith("SkillTree3.webp")
    assert index.trace_asset(1308, "Unknown trace", index=0) is None


def test_memosprite_icons_are_resolved_only_from_unique_real_files(index):
    assets = index.cache_dir / index.version / "en" / "assets" / "skillicons"
    assets.mkdir(parents=True)
    for filename in ["SkillIcon_11415_Servant.webp", "SkillIcon_11415_ServantPassive.webp", "SkillIcon_18007_Servant01.webp"]:
        (assets / filename).write_bytes(b"icon")
    assert index.skill_asset(1415, "Memosprite Skill").relative_path.endswith("11415_Servant.webp")
    assert index.skill_asset(1415, "Memosprite Talent").relative_path.endswith("11415_ServantPassive.webp")
    assert index.skill_asset(8007, "Memosprite Skill").relative_path.endswith("18007_Servant01.webp")
    assert index.skill_asset(1512, "Memosprite Skill") is None
    (assets / "SkillIcon_11415_Servant02.webp").write_bytes(b"other icon")
    assert index.skill_asset(1415, "Memosprite Skill") is None
    assert index.skill_asset(1415, "Unrecognized Memosprite Skill") is None


def test_cached_property_icons_take_precedence_over_bundle(index):
    path = index.cache_dir / index.version / "en" / "assets" / "skillicons" / "IconEnergyRecovery.webp"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"cached icon")
    assert index.asset_file(index.stat_asset("Energy Regen Rate")) == path.resolve()
    assert index.asset_file({"relative_path": "../../outside.webp"}) is None


def test_project_bundle_contains_correct_energy_and_healing_icons(index):
    import hsr_cards
    root = Path(hsr_cards.__file__).resolve().parent
    for label, stem in [("Energy Regen Rate", "IconEnergyRecovery"), ("Outgoing Healing Boost", "IconHealRatio")]:
        bundled = root / "assets" / "prydwen_builds" / "property" / f"{stem}.webp"
        assert bundled.is_file()
        assert index.asset_file(index.stat_asset(label)) == bundled

@pytest.mark.parametrize("label", ["Energy Regen", "ENERGY REGEN", "ER", "ERR"])
def test_proven_energy_stat_aliases(index, label):
    assert index.stat_asset(label).relative_path.endswith("IconEnergyRecovery.webp")


@pytest.mark.parametrize("label", ["EFFECT HIT RATING", "Effect Hit Rating", "EHR", "Effect Hit Rate (Some EHR Light Cones)"])
def test_effect_hit_stat_aliases_and_source_qualifiers(index, label):
    assert index.stat_asset(label).relative_path.endswith("IconStatusProbability.webp")


@pytest.mark.parametrize("label", ["SPD (-1 SPD Build)", "SPD (Hyperspeed)"])
def test_source_speed_qualifiers_keep_the_speed_identity(index, label):
    assert index.stat_asset(label).relative_path.endswith("IconSpeed.webp")


def test_combined_or_non_stat_labels_are_not_given_an_arbitrary_icon(index):
    for label in ["Anything", "Note on Planar Sphere", "ATK & Physical DMG Boost", "Recommended DPS Build"]:
        assert index.stat_asset(label) is None


def test_short_skill_aliases_match_the_same_real_memosprite_file(index):
    folder = index.cache_dir / index.version / "en" / "assets" / "skillicons"
    folder.mkdir(parents=True)
    (folder / "SkillIcon_11415_Servant.webp").write_bytes(b"skill")
    (folder / "SkillIcon_11415_ServantPassive.webp").write_bytes(b"talent")
    for label in ["Memo Skill", "M.Skill"]:
        assert index.skill_asset(1415, label) == index.skill_asset(1415, "Memosprite Skill")
    for label in ["Memo Talent", "M.Talent"]:
        assert index.skill_asset(1415, label) == index.skill_asset(1415, "Memosprite Talent")
    assert index.skill_asset(1308, "Ult") == index.skill_asset(1308, "Ultimate")
    assert index.skill_asset(1308, "Basic (Healing Focus) or Talent") is None
