"""Prydwen build teams source extraction without network access."""
from __future__ import annotations


import re


from pathlib import Path


from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from ..models import AssetRef, EditorTeam, EditorTeamMember, EditorTeamSlot, Synergy, TeamMode, TeamVariant

from ..assets import NanokaIndex, clean_text


from .build_common import _find_header, _text


TEAM_MODES = (
    ("moc", "Memory of Chaos"),
    ("pf", "Pure Fiction"),
    ("as", "Apocalyptic Shadow"),
    ("anomaly", "Anomaly Arbitration"),
)


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

