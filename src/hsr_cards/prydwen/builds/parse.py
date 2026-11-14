"""Turn rendered Prydwen HTML into the stable BuildCardData schema.

Prydwen serves Next SSR markup and uses the same ``detailed-cones`` class
for light-cone rows and relic rows. Classification therefore uses the icon
subtree, not only the outer wrapper. Each parser is defensive: a missing block
produces a warning and an empty list rather than a guessed recommendation.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .models import (
    AssetRef,
    BuildCardData,
    CharacterIdentity,
    CharacterStats,
    EditorTeam,
    EditorTeamMember,
    EditorTeamSlot,
    InvestmentGuide,
    InvestmentOption,
    LightConeRecommendation,
    RelicRecommendation,
    RelicWeightGroup,
    SkillInfo,
    SourceMeta,
    StatChoice,
    StatTarget,
    Synergy,
    TeamMode,
    TeamVariant,
    TraceBonus,
    TracePriority,
    TraceStep,
    WeightClass,
)
from .nanoka import (
    NanokaIndex,
    clean_text,
    normalize_name,
    parse_rarity,
    parse_score,
    parse_superimposition,
)

ELEMENT_LABELS = {
    "physical": "Physical",
    "fire": "Fire",
    "ice": "Ice",
    "thunder": "Lightning",
    "lightning": "Lightning",
    "wind": "Wind",
    "quantum": "Quantum",
    "imaginary": "Imaginary",
}
PATH_LABELS = {
    "destruction": "Destruction",
    "the hunt": "The Hunt",
    "hunt": "The Hunt",
    "erudition": "Erudition",
    "harmony": "Harmony",
    "nihility": "Nihility",
    "preservation": "Preservation",
    "abundance": "Abundance",
    "remembrance": "Remembrance",
    "elation": "Elation",
}
TEAM_MODES = (
    ("moc", "Memory of Chaos"),
    ("pf", "Pure Fiction"),
    ("as", "Apocalyptic Shadow"),
    ("anomaly", "Anomaly Arbitration"),
)
WEIGHT_BY_HEADING = {
    "best": WeightClass.BEST,
    "specialist": WeightClass.SPECIALIST,
    "general": WeightClass.GENERAL,
    "specific": WeightClass.SPECIFIC,
    "alternative": WeightClass.ALTERNATIVE,
}


def _text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    # Comment boundaries in Next SSR split S1, percentages and piece counts.
    text = " ".join(tag.get_text(" ", strip=True).split())
    text = re.sub(r"\(\s*S\s*(\d)\s*\)", r"(S\1)", text, flags=re.I)
    text = re.sub(r"(?<=\d)\s+(?=%)", "", text)
    text = re.sub(r"\+\s+(?=\d)", "+", text)
    text = re.sub(r"\(\s*(\d)\s*-\s*PC\s*\)", r"(\1-PC)", text, flags=re.I)
    return text


def _find_header(soup: Tag, label: str) -> Tag | None:
    target = label.casefold()
    for header in soup.select(".content-header, h1, h2, h3, h6"):
        if _text(header).casefold() == target:
            return header
    for header in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if _text(header).casefold() == target:
            return header
    return None


def _section_after(header: Tag, stop: Iterable[str]) -> list[Tag]:
    result: list[Tag] = []
    stop_set = {value.casefold() for value in stop}
    for sibling in header.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.select_one(".content-header") or sibling.name in {"h1", "h2", "h3", "h6"}:
            heading = _text(sibling.select_one(".content-header") or sibling)
            if heading.casefold() in stop_set:
                break
        result.append(sibling)
    return result


def _identity(soup: BeautifulSoup, slug: str, source_url: str, nanoka: NanokaIndex) -> CharacterIdentity:
    top = soup.select_one("div.character-top") or soup
    h1 = top.select_one("h1")
    name = _text(h1.find("strong")) if h1 else ""
    name = name or (_text(h1).split(" BEST BUILD")[0] if h1 else slug.replace("-", " ").title())
    intro = soup.select_one("div.character-intro") or soup.select_one(".char-intro")
    page_text = _text(intro) if intro else ""
    rarity_match = re.search(r"([1-5])\s*(?:\u2605|stars?\b|star\b)", page_text, re.I)
    rarity = int(rarity_match.group(1)) if rarity_match else None
    element_match = re.search(r"from the\s+(.+?)\s+element", page_text, re.I)
    path_match = re.search(r"Path of\s+(.+?)(?:\.|$)", page_text, re.I)
    element = element_match.group(1).strip() if element_match else ""
    path = path_match.group(1).strip() if path_match else ""
    if not element:
        element_tag = top.select_one("strong.Ice, strong.Physical, strong.Fire, strong.Wind, strong.Lightning, strong.Quantum, strong.Imaginary")
        if element_tag:
            element = next((c for c in element_tag.get("class", []) if c.casefold() in ELEMENT_LABELS), "")
    element = ELEMENT_LABELS.get(element.casefold(), element or "Unknown")
    path = PATH_LABELS.get(path.casefold(), path or "Unknown")
    last_updated = None
    for paragraph in top.select("p"):
        text = _text(paragraph)
        if text.casefold().startswith("last updated:"):
            last_updated = text.split(":", 1)[1].strip() or None
            break
    # Resolve form-specific slugs before reused names (March/Trailblazer).
    record = nanoka._slug_character(slug) or nanoka.character(name=name)
    identifier = int(record["id"]) if record and record.get("id") else None
    identity = CharacterIdentity(
        name=name, slug=slug, title=_text(h1.select_one("span.sub")) or None if h1 else None,
        rarity=rarity, element=element, path=path, last_updated=last_updated,
        description=" ".join(_text(p) for p in soup.select("div.character-intro div.char-intro .rte-plain p")) or None,
        source_url=source_url, nanoka_id=identifier,
    )
    if identifier is not None:
        identity.icon = nanoka.character_icon(identifier)
        identity.round_icon = nanoka.character_round_icon(identifier)
        identity.drawcard = nanoka.character_drawcard(identifier)
    identity.element_icon = nanoka.element_asset(element)
    identity.path_icon = nanoka.path_asset(path)
    return identity


def _stats(soup: BeautifulSoup) -> CharacterStats:
    stats = CharacterStats()
    block = soup.select_one("div.stats")
    if not block:
        return stats
    labels = {"HP": "hp", "ATK": "atk", "DEF": "defence", "Speed": "speed", "SPD": "speed"}
    pending: str | None = None
    for cell in block.find_all(["div", "span", "p"], recursive=True):
        text = _text(cell)
        if text in labels and not any(_text(child) for child in cell.find_all(recursive=False)):
            pending = labels[text]
            continue
        if pending and re.fullmatch(r"\d+", text):
            setattr(stats, pending, int(text))
            pending = None
    return stats


def _weight_for_heading(heading: str) -> WeightClass:
    # "Best Specialist" is a specialist restriction, not general best-in-slot.
    for key in ("specialist", "specific", "alternative", "general", "best"):
        if key in heading.casefold():
            return WEIGHT_BY_HEADING[key]
    return WeightClass.ALTERNATIVE


def _is_relic_block(entry: Tag) -> bool:
    return bool(entry.select_one("div.hsr-set-image.relic, div.hsr-set-image.planetary"))


def _is_cone_block(entry: Tag) -> bool:
    return bool(entry.select_one("div.hsr-cone-icon")) and not _is_relic_block(entry)


def _following_information(single: Tag) -> list[Tag]:
    """Only metadata immediately belonging to this ranked row.

    A selective find_next_sibling(class_="information") can skip the next row
    and steal its conditional explanation. Stop at the first other element.
    """
    result: list[Tag] = []
    sibling = single.find_next_sibling()
    while isinstance(sibling, Tag) and "information" in sibling.get("class", []):
        result.append(sibling)
        sibling = sibling.find_next_sibling()
    return result


def _parse_cones(section: Tag, nanoka: NanokaIndex, source_builds: list[dict] | None = None) -> list[LightConeRecommendation]:
    header = _find_header(section, "Best Light Cones")
    if not header:
        return []
    result: list[LightConeRecommendation] = []
    seen: set[tuple[str, int | None, str, str]] = set()
    heading = "Best Light Cones"
    for sibling in _section_after(header, ["Best Relic Sets", "Best Stats"]):
        if sibling.name in {"h2", "h3", "h4", "h5", "h6"}:
            heading = _text(sibling) or heading
        entries = [sibling] if "detailed-cones" in sibling.get("class", []) else sibling.select(".detailed-cones")
        for entry in entries:
            if not _is_cone_block(entry):
                continue
            for single in entry.select("div.single-cone"):
                card = single.select_one(".pw-accordion-button") or single
                name = _text(card.select_one(".hsr-set-name"))
                if not name:
                    continue
                sup = parse_superimposition(_text(card.select_one(".cone-super")))
                score_text = _text(single.select_one(".percentage"))
                rank = int(score_text) if score_text.isdigit() and int(score_text) > 0 else None
                score, score_text = parse_score(score_text)
                key = (normalize_name(name), sup, score_text or "", heading)
                if key in seen:
                    continue
                seen.add(key)
                icon = card.select_one(".hsr-cone-icon")
                rarity = parse_rarity(" ".join(icon.get("class", []))) if icon else None
                information = _following_information(single)
                reason = next((node for node in information if "with-padding" not in node.get("class", [])), None)
                endgame: dict[str, str] = {}
                usage = None
                for pill in (pill for node in information for pill in node.select(".hsr-special-data .pill")):
                    text = _text(pill)
                    if ":" in text:
                        key_name, value = (part.strip() for part in text.split(":", 1))
                        if key_name.casefold() == "usage":
                            usage = value
                        else:
                            endgame[key_name] = value
                record = nanoka.light_cone(name)
                source_type = None
                for source_row in source_builds or []:
                    if (normalize_name(str(source_row.get("cone_name", ""))) == normalize_name(name)
                            and source_row.get("dupes") == sup
                            and str(source_row.get("percentage") or "").replace(" ", "") == (score_text or "").replace(" ", "")):
                        source_type = source_row.get("build_type")
                        break
                specialist = "specialist" in heading.casefold() or str(source_type).casefold() == "special"
                weight = WeightClass.SPECIALIST if specialist else WeightClass.BEST if not result or rank == 1 else WeightClass.ALTERNATIVE
                result.append(LightConeRecommendation(
                    name=name, heading=heading, build_type=source_type,
                    superimposition=sup, rarity=rarity, rank=rank,
                    score=score, score_text=score_text, weight=weight,
                    reason=_text(reason) or None, usage=usage, endgame_notes=endgame,
                    asset=nanoka.light_cone_asset(record) if record else None,
                ))
    return result


def _parse_relics(section: Tag, nanoka: NanokaIndex) -> tuple[list[RelicWeightGroup], list[AssetRef]]:
    header = _find_header(section, "Best Relic Sets")
    if not header:
        return [], []
    groups: list[RelicWeightGroup] = []
    mixed: list[AssetRef] = []
    heading = "Best Relic Sets"
    for node in header.next_elements:
        if not isinstance(node, Tag):
            continue
        if "content-header" in node.get("class", []):
            if node is header:
                continue
            break
        if node.name in {"h3", "h6"}:
            label = _text(node)
            if "set" in label.casefold():
                heading = label
        if node.name == "ul" and "with-sets" in node.get("class", []):
            for item in node.select("li"):
                name = _text(item.select_one(".hsr-name") or item)
                record = nanoka.relic(name)
                if record:
                    ref = nanoka.relic_asset(record)
                    if ref not in mixed:
                        mixed.append(ref)
        if "detailed-cones" not in node.get("class", []) or not _is_relic_block(node):
            continue
        icon_planar = bool(node.select_one(".hsr-set-image.planetary"))
        slot = "planar" if icon_planar else "cavern"
        group = RelicWeightGroup(heading=heading, weight=_weight_for_heading(heading), slot=slot)
        for row_index, single in enumerate(node.select("div.single-cone")):
            card = single.select_one(".pw-accordion-button") or single
            names = single.select(".hsr-set-name")
            if not names:
                continue
            score_text = _text(single.select_one(".percentage"))
            score, score_text = parse_score(score_text)
            rank = int(score_text) if score_text and score_text.isdigit() and int(score_text) > 0 else None
            information = _following_information(single)
            reason = next((node for node in information if "with-padding" not in node.get("class", [])), None)
            usage = None
            special = next((node for node in information if "with-padding" in node.get("class", [])), None)
            if special is not None:
                for pill in special.select(".pill"):
                    if _text(pill).casefold().startswith("usage:"):
                        usage = _text(pill).split(":", 1)[1].strip()
            combination = f"{len(groups)}:{row_index}" if len(names) > 1 else None
            for name_tag in names:
                raw_name = _text(name_tag)
                match = re.search(r"\(\s*([24])\s*-PC\s*\)", raw_name, re.I)
                pieces = int(match.group(1)) if match else None
                name = re.sub(r"\s*\(\s*[24]\s*-PC\s*\)", "", raw_name, flags=re.I).strip()
                if not name:
                    continue
                record = nanoka.relic(name)
                group.recommendations.append(RelicRecommendation(
                    name=name, pieces=pieces, rank=rank, slot=slot, score=score,
                    score_text=score_text, weight=group.weight, reason=_text(reason) or None,
                    usage=usage, flex=slot == "cavern" and pieces == 2,
                    combination_id=combination, asset=nanoka.relic_asset(record) if record else None,
                ))
        if group.recommendations:
            groups.append(group)
    return groups, mixed


def _parse_stats(section: Tag, nanoka: NanokaIndex) -> tuple[list[StatChoice], list[str], str | None, list[StatTarget], list[str]]:
    choices: list[StatChoice] = []
    for box in section.select(".main-stats .box"):
        slot = _text(box.select_one(".stats-header"))
        if not slot:
            continue
        values = [_text(stat.select_one("span:last-child") or stat) for stat in box.select(".hsr-stat")]
        choices.append(StatChoice(
            slot=slot, values=values, operators=[_text(op) for op in box.select(".order")],
            raw_text=_text(box), icons=[nanoka.stat_asset(value) for value in values],
        ))
    substats_raw = None
    for box in section.select(".sub-stats"):
        if _text(box).casefold().startswith("substats:"):
            substats_raw = _text(box).split(":", 1)[1].strip() or None
            break
    # Keep each equality tier intact; raw wording remains the canonical order.
    substats = [part.strip() for part in re.split(r"\s*>(?!=)\s*", substats_raw or "") if part.strip()]
    targets: list[StatTarget] = []
    notes: list[str] = []
    header = _find_header(section, "Recommended endgame stats")
    if header:
        sibling = header.find_next_sibling()
        raw = sibling.select_one(".raw") if sibling else None
        raw = raw or sibling
        if raw:
            top_list = raw.select_one("ul")
            if top_list:
                for item in top_list.find_all("li", recursive=False):
                    clone = BeautifulSoup(str(item), "lxml").select_one("li")
                    nested = [_text(child) for child in clone.select("li")]
                    for child in clone.select("ul, ol"):
                        child.decompose()
                    text = _text(clone)
                    if ":" in text:
                        stat, target = (value.strip() for value in text.split(":", 1))
                        targets.append(StatTarget(stat=stat, target=target, notes=nested, icon=nanoka.stat_asset(stat)))
                    elif text:
                        notes.append(text)
            notes.extend(_text(paragraph) for paragraph in raw.find_all("p", recursive=False) if _text(paragraph))
    return choices, substats, substats_raw, targets, notes


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


def _character_links(tag: Tag, nanoka: NanokaIndex) -> tuple[list[str], list[AssetRef | None]]:
    names: list[str] = []
    assets: list[AssetRef | None] = []
    for anchor in tag.select("a[href*='/star-rail/characters/']"):
        name_tag = anchor.select_one(".inline-name")
        img = anchor.select_one("img")
        name = _text(name_tag) if name_tag else (img.get("alt", "") if img else "") or anchor.get("title", "") or _text(anchor)
        if not name:
            continue
        slug = urlparse(anchor.get("href", "")).path.rstrip("/").rsplit("/", 1)[-1]
        identifier = nanoka.character_id(slug=slug) or nanoka.character_id(name=name)
        names.append(name)
        assets.append(nanoka.character_icon(identifier) if identifier is not None else None)
    return names, assets


def _parse_synergies(tab: Tag, nanoka: NanokaIndex) -> tuple[str | None, list[Synergy]]:
    header = _find_header(tab, "Synergy")
    if not header:
        return None, []
    result: list[Synergy] = []
    intro: str | None = None
    for sibling in header.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.select_one(".content-header") or sibling.name in {"h2", "h3"}:
            text = _text(sibling.select_one(".content-header") or sibling)
            if text.casefold() == "teams":
                break
        if sibling.name == "ul" and "bigger-margin" in (sibling.get("class") or []):
            for item in sibling.find_all("li", recursive=False):
                names, assets = _character_links(item, nanoka)
                note = _text(item)
                for name in names:
                    note = re.sub(rf"^{re.escape(name)}\s*-?\s*", "", note, flags=re.I)
                result.append(Synergy(characters=names, character_assets=assets, note=note.strip()))
        elif not intro and (sibling.name == "p" or "info-box" in sibling.get("class", [])):
            intro = _text(sibling) or None
    return intro, result


def _parse_team_rows(container: Tag, nanoka: NanokaIndex) -> list[TeamVariant]:
    variants: list[TeamVariant] = []
    for row in container.select("div.team-row"):
        info = row.select_one(".column.info")
        character_column = row.select_one(".column.characters")
        if info is None or character_column is None:
            continue
        performance: dict[str, str] = {}
        rank = None
        rate = None
        for paragraph in info.find_all("p", recursive=False):
            text = _text(paragraph)
            if text.casefold().startswith("rank "):
                match = re.search(r"Rank\s+(\d+)", text, re.I)
                rank = int(match.group(1)) if match else None
            elif text.casefold().startswith("app. rate:"):
                rate = text.split(":", 1)[1].strip()
            elif ":" in text:
                key, value = (part.strip() for part in text.split(":", 1))
                performance[key] = value
        names, assets = _character_links(character_column, nanoka)
        if names:
            variants.append(TeamVariant(characters=names, character_assets=assets, rank=rank, application_rate=rate, performance=performance))
    return variants


def _find_team_container(header: Tag) -> Tag | None:
    node: Tag | None = header
    while node is not None:
        node = node.find_next_sibling()
        while node is not None and isinstance(node, Tag):
            classes = node.get("class") or []
            if any("team-container" in value for value in classes):
                return node
            if "tier-list-switcher" in classes:
                node = node.find_next_sibling()
                continue
            if "content-header" in classes:
                return None
            node = node.find_next_sibling()
        break
    return None


def _parse_teams_from_html(html: str, nanoka: NanokaIndex) -> list[TeamVariant]:
    soup = BeautifulSoup(html, "lxml")
    for header in soup.select("div.tab-inside > .content-header"):
        if _text(header).casefold() != "teams":
            continue
        container = _find_team_container(header)
        if container:
            return _parse_team_rows(container, nanoka)
    return []


def _parse_editorial_teams(tab: Tag, nanoka: NanokaIndex) -> list[EditorTeam]:
    teams: list[EditorTeam] = []
    for block in tab.select(".character-teams"):
        name = _text(block.select_one(".team-header"))
        if not name:
            continue
        members: list[EditorTeamMember] = []
        slots: list[EditorTeamSlot] = []
        for slot_index, role_box in enumerate(block.select(".single-team .with-role")):
            role = _text(role_box.select_one(".role")) or None
            slot_members: list[EditorTeamMember] = []
            for character in role_box.select(".character"):
                names, assets = _character_links(character, nanoka)
                for member_name, asset in zip(names, assets):
                    member = EditorTeamMember(name=member_name, role=role, slot=slot_index, asset=asset)
                    slot_members.append(member)
                    members.append(member)
            if slot_members:
                slots.append(EditorTeamSlot(role=role, members=slot_members))
        if members:
            notes = [_text(p) for p in block.select(".team-note, .team-notes, .information") if _text(p)]
            teams.append(EditorTeam(name=name, members=members, slots=slots, note=" ".join(notes) or None))
    return teams


def _next_character_props(soup: BeautifulSoup, slug: str) -> dict:
    """Decode public SSR props as data only, never execute downloaded JavaScript.

    Next's Flight stream embeds one or more JSON records per push. A record
    may span script boundaries, so join chunks before reading complete lines.
    Ignore import/text/reference records; only a matching character's object
    may supply analytics and source metadata.
    """
    chunks: list[str] = []
    for script in soup.select("script"):
        content = script.string or script.get_text()
        prefix = "self.__next_f.push("
        if not content.startswith(prefix) or not content.endswith(")"):
            continue
        try:
            push = json.loads(content[len(prefix):-1])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(push, list) and len(push) > 1 and push[0] == 1 and isinstance(push[1], str):
            chunks.append(push[1])

    def locate(value):
        if isinstance(value, dict):
            character = value.get("character")
            if isinstance(character, dict) and character.get("slug") == slug:
                return value
            for child in value.values():
                found = locate(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = locate(child)
                if found:
                    return found
        return None

    for line in "".join(chunks).splitlines():
        match = re.match(r"^[0-9a-f]+:([\[{].*)$", line)
        if match:
            try:
                found = locate(json.loads(match.group(1)))
            except (json.JSONDecodeError, TypeError, RecursionError):
                continue
            if found:
                return found
    return {}


def _parse_embedded_teams(props: dict, nanoka: NanokaIndex, raw_path: Path | None) -> list[TeamMode]:
    analytics = props.get("analytics")
    if not isinstance(analytics, dict):
        return []
    catalog = {row["slug"]: row for row in props.get("tierRatings", []) if isinstance(row, dict) and row.get("slug")}
    catalog.update({row["slug"]: row for row in props.get("characters", []) if isinstance(row, dict) and row.get("slug")})
    owner = props.get("character")
    if isinstance(owner, dict) and owner.get("slug"):
        catalog[owner["slug"]] = owner
    # The page renders 99.99 cycle sentinels and missing/zero scores as dashes.
    # raw_metrics retains the exact source values for later audit.
    def display_metric(value, cycle):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return "-"
        if value == 0 or (cycle and value == 99.99):
            return "-"
        return f"{value:g}"

    modes: list[TeamMode] = []
    for key, label in TEAM_MODES:
        prefix = "aa" if key == "anomaly" else key
        rows = analytics.get(f"{prefix}Teams")
        if not isinstance(rows, list):
            continue
        variants: list[TeamVariant] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            slugs = [row.get(f"char_{number}") for number in ("one", "two", "three", "four")]
            if any(not isinstance(value, str) or not value for value in slugs):
                continue
            names: list[str] = []
            assets: list[AssetRef | None] = []
            for member_slug in slugs:
                record = catalog.get(member_slug, {})
                nanoka_record = nanoka._slug_character(member_slug)
                name = record.get("name") or (clean_text(nanoka_record.get("en")) if nanoka_record else None) or member_slug
                identifier = int(nanoka_record["id"]) if nanoka_record else nanoka.character_id(name=name)
                names.append(name)
                assets.append(nanoka.character_icon(identifier) if identifier is not None else None)
            cycle = key in {"moc", "anomaly"}
            metric = "Avg. cycles" if cycle else "Avg. score"
            rate = row.get("app_rate")
            rank = row.get("rank")
            variants.append(TeamVariant(
                characters=names, character_assets=assets, character_slugs=slugs,
                rank=rank if isinstance(rank, int) and rank > 0 else None,
                application_rate=f"{rate:g}%" if isinstance(rate, (int, float)) else None,
                performance={metric: display_metric(row.get("avg_round"), cycle), f"{metric} (E1+)": display_metric(row.get("avg_round_c1"), cycle)},
                raw_metrics={k: row.get(k) for k in ("rank", "app_rate", "avg_round", "avg_round_c1") if isinstance(row.get(k), (int, float)) or row.get(k) is None},
            ))
        phase = analytics.get(f"{prefix}Phase")
        modes.append(TeamMode(
            mode=key, label=label, variants=variants, source_file=raw_path.name if raw_path else None,
            source_path=f"next.analytics.{prefix}Teams", phase=phase.get("phase") if isinstance(phase, dict) else None,
        ))
    return modes


def _parse_teams(tab: Tag, nanoka: NanokaIndex, raw_path: Path | None = None) -> list[TeamMode]:
    modes: list[TeamMode] = []
    selected = tab.select_one(".tier-list-switcher .option.selected")
    selected_label = _text(selected).casefold() if selected else None
    for index, (key, label) in enumerate(TEAM_MODES):
        variants: list[TeamVariant] = []
        source_file = None
        if selected_label == label.casefold():
            variants = _parse_team_rows(tab, nanoka)
            source_file = raw_path.name if raw_path else None
        if raw_path is not None:
            mode_path = raw_path.with_name(f"{raw_path.stem}.{index}.html")
            if mode_path.is_file():
                mode_soup = BeautifulSoup(mode_path.read_text(encoding="utf-8"), "lxml")
                mode_selected = mode_soup.select_one(".tier-list-switcher .option.selected")
                # Never relabel a snapshot of another mode, even if filename matches.
                if mode_selected and _text(mode_selected).casefold() == label.casefold():
                    variants = _parse_team_rows(mode_soup, nanoka)
                    source_file = mode_path.name
        modes.append(TeamMode(mode=key, label=label, variants=variants, source_file=source_file))
    return modes


def parse_html(html: str, *, source_url: str, nanoka: NanokaIndex, raw_path: Path | None = None) -> BuildCardData:
    """Parse a cached snapshot only; never performs network requests or approvals."""
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

