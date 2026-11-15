"""Prydwen builds source extraction without network access."""
from __future__ import annotations

import hashlib

import json


from datetime import datetime, timezone

from pathlib import Path


from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..models import BuildCardData, SourceMeta, TracePriority

from ..assets import NanokaIndex


from .build_common import _identity, _next_character_props, _stats, _text
from .build_gear import _parse_cones, _parse_relics, _parse_stats
from .build_teams import TEAM_MODES, _parse_editorial_teams, _parse_embedded_teams, _parse_synergies, _parse_teams
from .build_skills import _parse_investment, _parse_major_traces, _parse_review_notes, _parse_skills, _parse_trace, _parse_trace_bonus, _trace_steps


def parse_html(html: str, *, source_url: str, nanoka: NanokaIndex, raw_path: Path | None = None) -> BuildCardData:
    """Return a draft BuildCardData from source HTML and a read-only Nanoka index.

    source_url establishes the source character slug. Optional raw_path locates
    provenance metadata and saved team-mode snapshots; these local files may be
    read, but are never written. Missing source sections yield warnings and empty
    fields. Source conditions, form identity, and mode associations are preserved.
    No network or approval operations occur; invalid model data raises validation
    errors and unreadable optional files can raise filesystem errors.
    """
    soup = BeautifulSoup(html, "lxml")
    slug = urlparse(source_url).path.rstrip("/").rsplit("/", 1)[-1]
    identity = _identity(soup, slug, source_url, nanoka)
    section = soup.select_one("div.section-build")
    tab = section.find_parent("div", class_="tab-inside") if section else None
    tab = tab or section
    warnings: list[str] = []
    props = _next_character_props(soup, slug)
    cones = _parse_cones(section, nanoka, props.get("coneBuilds")) if section else []
    relics, mixed = _parse_relics(section, nanoka) if section else ([], [])
    choices, substats, substats_raw, targets, target_notes = _parse_stats(section, nanoka) if section else ([], [], None, [], [])
    trace = _parse_trace(section) if section else TracePriority()
    trace.skill_steps = _trace_steps(trace, identity.nanoka_id, nanoka)
    synergy_intro, synergies = _parse_synergies(tab, nanoka) if tab else (None, [])
    teams = _parse_embedded_teams(props, nanoka, raw_path) or (_parse_teams(tab, nanoka, raw_path) if tab else [])
    editorial = _parse_editorial_teams(tab, nanoka) if tab else []
    updates: dict[str, str] = {}
    for entry in soup.select(".last-update .element"):
        name, value = _text(entry.select_one(".name")), _text(entry.select_one(".info"))
        if name and value:
            updates[name] = value
    source_character = props.get("character", {})
    if isinstance(source_character, dict) and source_character.get("updatedAt"):
        updates["updatedAt"] = str(source_character["updatedAt"])
    selected = tab.select_one(".tier-list-switcher .option.selected") if tab else None
    primary_mode = next((key for key, label in TEAM_MODES if selected and _text(selected).casefold() == label.casefold()), None)
    fetched_at = None
    generated_at = datetime.now(timezone.utc)
    stat_builds = props.get("statBuilds", [])
    build_name = stat_builds[0].get("name") if stat_builds and isinstance(stat_builds[0], dict) else None
    if len(stat_builds) > 1:
        warnings.append("Multiple named stat builds in source; verify build-specific associations")
    if raw_path is not None:
        metadata_path = raw_path.with_suffix(".meta.json")
        if metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text("utf-8"))
                fetched_at = datetime.fromisoformat(metadata["fetched_at"])
                generated_at = fetched_at
            except (KeyError, ValueError, TypeError, json.JSONDecodeError):
                warnings.append("Raw metadata has no valid fetched_at timestamp")
    source_meta = SourceMeta(
        url=source_url, fetched_at=fetched_at, last_updated=identity.last_updated,
        last_review_update=next((v for k, v in updates.items() if "review" in k.casefold()), None),
        last_major_build_update=next((v for k, v in updates.items() if "major build" in k.casefold()), None),
        primary_mode=primary_mode, html_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        raw_file=raw_path.name if raw_path else None, website_updates=updates,
    )
    bonuses = _parse_trace_bonus(soup, nanoka)
    skills = _parse_skills(soup, identity.nanoka_id, nanoka)
    major_traces = _parse_major_traces(soup, identity.nanoka_id, nanoka)
    diagnostics = {
        "has_build_section": bool(section), "has_light_cones": bool(cones),
        "has_relics": bool(relics), "has_main_stats": bool(choices),
        "has_stat_targets": bool(targets), "has_trace_priority": bool(trace.skills),
        "has_trace_bonuses": bool(bonuses), "has_skills": bool(skills),
        "has_teams": any(mode.variants for mode in teams),
        "has_editorial_teams": bool(editorial), "has_synergies": bool(synergies),
        "has_source_updated": bool(identity.last_updated),
    }
    for key, message in (
        ("has_build_section", "Build and teams section not found in the saved HTML"),
        ("has_light_cones", "No light cones parsed"), ("has_relics", "No relic sets parsed"),
        ("has_main_stats", "No main stats parsed"), ("has_source_updated", "No website last-updated date parsed"),
    ):
        if not diagnostics[key]:
            warnings.append(message)
    if not synergies and not editorial and not any(mode.variants for mode in teams):
        warnings.append("No teams or synergies parsed")
    if identity.nanoka_id is None:
        warnings.append("Nanoka character id could not be resolved")
    if identity.rarity is None or identity.element == "Unknown" or identity.path == "Unknown":
        warnings.append("Character identity is incomplete; verify rarity, element and path")
    if any(asset is None for synergy in synergies for asset in synergy.character_assets):
        warnings.append("Some synergy character assets could not be resolved")
    notes: list[str] = []
    if section:
        # Preserve qualifiers/calculation assumptions that sit between ranked rows.
        for child in section.find_all("p", recursive=False):
            if _text(child):
                notes.append(_text(child))
        for block in section.select(".build-stats > .information"):
            if _text(block):
                notes.append(_text(block))
    team_comments: list[str] = []
    if tab:
        for paragraph in tab.find_all("p", recursive=False):
            text = _text(paragraph)
            if text:
                team_comments.append(text)
    return BuildCardData(
        generated_at=generated_at, source=source_url, source_meta=source_meta,
        character=identity, build_name=build_name, stats=_stats(soup), light_cones=cones, relic_sets=relics,
        mixed_relic_sets=mixed, main_stats=choices, substats=substats, substats_raw=substats_raw,
        stat_targets=targets, stat_target_notes=target_notes, trace_priority=trace,
        trace_bonuses=bonuses, skills=skills, major_traces=major_traces,
        investment=_parse_investment(soup, nanoka), review_notes=_parse_review_notes(soup),
        editorial_teams=editorial, synergies=synergies, synergy_intro=synergy_intro,
        teams=teams, team_comments=team_comments, notes=notes, warnings=warnings, diagnostics=diagnostics,
    )

