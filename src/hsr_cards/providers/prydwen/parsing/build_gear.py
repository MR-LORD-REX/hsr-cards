"""Prydwen build gear source extraction without network access."""
from __future__ import annotations


import re


from bs4 import BeautifulSoup, Tag

from ..models import AssetRef, LightConeRecommendation, RelicRecommendation, RelicWeightGroup, StatChoice, StatTarget, WeightClass

from ..assets import NanokaIndex, normalize_name, parse_rarity, parse_score, parse_superimposition


from .build_common import _find_header, _section_after, _text


WEIGHT_BY_HEADING = {
    "best": WeightClass.BEST,
    "specialist": WeightClass.SPECIALIST,
    "general": WeightClass.GENERAL,
    "specific": WeightClass.SPECIFIC,
    "alternative": WeightClass.ALTERNATIVE,
}


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

