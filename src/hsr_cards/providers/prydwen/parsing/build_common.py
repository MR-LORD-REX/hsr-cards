"""Prydwen build common source extraction without network access."""
from __future__ import annotations


import json

import re


from typing import Iterable


from bs4 import BeautifulSoup, Tag

from ..models import CharacterIdentity, CharacterStats

from ..assets import NanokaIndex


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

