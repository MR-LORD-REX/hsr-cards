"""Prydwen build skills source extraction without network access."""
from __future__ import annotations


import re


from bs4 import BeautifulSoup, Tag

from ..models import AssetRef, InvestmentGuide, InvestmentOption, SkillInfo, TraceBonus, TracePriority, TraceStep

from ..assets import NanokaIndex


from .build_common import _find_header, _section_after, _text


def _parse_trace(section: Tag) -> TracePriority:
    priority = TracePriority()
    for box in section.select(".build-stats .sub-stats"):
        text = _text(box)
        if text.casefold().startswith("skills priority:"):
            priority.skills = text.split(":", 1)[1].strip()
        elif text.casefold().startswith("major traces priority:"):
            priority.major_traces = text.split(":", 1)[1].strip()
    priority.raw_text = " | ".join(value for value in (priority.skills, priority.major_traces) if value) or None
    priority.skill_operators = re.findall(r">=|<=|[>=/]|\u2265|\u2264", priority.skills or "")
    return priority


def _icon_for_stat(nanoka: NanokaIndex, label: str | None) -> AssetRef | None:
    return nanoka.stat_asset(label)


def _parse_trace_bonus(soup: BeautifulSoup, nanoka: NanokaIndex) -> list[TraceBonus]:
    header = _find_header(soup, "Minor Traces (total)")
    if not header:
        return []
    container = header.find_next_sibling("div")
    if not container:
        return []
    result: list[TraceBonus] = []
    for box in container.select("div.box.trace"):
        stat = _text(box.select_one(".hsr-stat") or box)
        value = _text(box.select_one(".value"))
        if not stat or not value:
            continue
        result.append(TraceBonus(stat=stat, value=value, icon=nanoka.stat_asset(stat)))
    return result


def _parse_skills(soup: BeautifulSoup, nanoka_id: int | None, nanoka: NanokaIndex) -> list[SkillInfo]:
    header = _find_header(soup, "Skills")
    if not header:
        return []
    container = header.find_next_sibling("div")
    if not container:
        return []
    skills: list[SkillInfo] = []
    for box in container.select("div.box"):
        icon_tag = box.select_one(".skill-icon")
        name = _text(box.select_one(".skill-name"))
        if not icon_tag or not name:
            continue
        kind = _text(icon_tag)
        label = kind
        skills.append(
            SkillInfo(
                kind=kind,
                name=name,
                description=_text(box.select_one(".skill-with-coloring")) or None,
                icon=nanoka.skill_asset(nanoka_id, label),
            )
        )
    return skills


def _parse_major_traces(soup: BeautifulSoup, nanoka_id: int | None, nanoka: NanokaIndex) -> list[SkillInfo]:
    header = _find_header(soup, "Major Traces")
    if not header:
        return []
    container = header.find_next_sibling("div")
    if not container:
        return []
    traces: list[SkillInfo] = []
    for index, box in enumerate(container.select("div.box")):
        icon_tag = box.select_one(".skill-icon")
        name = _text(box.select_one(".skill-name"))
        if not icon_tag or not name:
            continue
        level = _text(icon_tag).split(" ", 1)[0]
        traces.append(
            SkillInfo(
                kind="Major Trace",
                name=name,
                trace_level=level,
                description=_text(box.select_one(".skill-with-coloring")) or None,
                icon=nanoka.trace_asset(nanoka_id, level, index),
            )
        )
    return traces


def _trace_steps(priority: TracePriority, nanoka_id: int | None, nanoka: NanokaIndex) -> list[TraceStep]:
    """Turn the priority string into ordered icon labels without changing it."""
    if not priority.skills:
        return []
    parts = re.split(r"\s*(>=|<=|[>=/]|\u2265|\u2264)\s*", priority.skills)
    steps: list[TraceStep] = []
    for index in range(0, len(parts), 2):
        label = parts[index].strip()
        if label:
            steps.append(TraceStep(label=label, asset=nanoka.skill_asset(nanoka_id, label)))
    return steps


def _parse_review_notes(soup: BeautifulSoup) -> list[str]:
    header = _find_header(soup, "Pros & Cons")
    if not header:
        return []
    container = header.find_next_sibling("div")
    if not container:
        return []
    notes: list[str] = []
    for side in container.select("div.box"):
        heading = _text(side.select_one("h5"))
        for item in side.select("li"):
            text = _text(item)
            if text:
                notes.append(f"{heading}: {text}" if heading else text)
    return notes


def _parse_investment(soup: BeautifulSoup, nanoka: NanokaIndex) -> InvestmentGuide:
    # The profile Eidolon list is a kit inventory, never an investment order.
    # Populate only when Prydwen explicitly publishes an ordered priority.
    guide = InvestmentGuide()
    for label in ("Eidolon priority", "Investment priority", "Recommended investment"):
        header = _find_header(soup, label)
        if not header:
            continue
        for sibling in _section_after(header, ["Synergy", "Teams", "Best Light Cones", "Best Relic Sets"]):
            for item in sibling.select("ol > li"):
                if _text(item):
                    guide.order.append(InvestmentOption(label=_text(item)))
            if sibling.name == "p" and _text(sibling):
                guide.notes.append(_text(sibling))
        break
    return guide

