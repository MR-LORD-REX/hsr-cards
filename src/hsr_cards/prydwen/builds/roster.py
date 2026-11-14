"""Build and resolve the Prydwen character roster."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .nanoka import NanokaIndex, clean_text, normalize_name

PRYDWEN_CHARACTERS_URL = "https://www.prydwen.gg/star-rail/characters"
PRYDWEN_BASE = "https://www.prydwen.gg/star-rail/characters"

_NON_HSR_MARKERS = {"ZZZ", "Honkai Impact", "Genshin Impact", "Wuthering Waves"}


@dataclass
class RosterEntry:
    slug: str
    name: str
    url: str
    nanoka_id: int | None = None
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "url": self.url,
            "nanoka_id": self.nanoka_id,
            "aliases": self.aliases,
        }


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1]


def _is_hsr_entry(label: str) -> bool:
    upper = label.upper()
    return not any(marker.upper() in upper for marker in _NON_HSR_MARKERS)


def parse_roster_html(html: str, nanoka: NanokaIndex | None = None) -> list[RosterEntry]:
    """Extract character links from a rendered Prydwen characters index."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entries: dict[str, RosterEntry] = {}
    for anchor in soup.select("a[href*='/star-rail/characters/']"):
        href = anchor.get("href") or ""
        if not href or href.rstrip("/").endswith("/characters"):
            continue
        slug = slug_from_url(href)
        if not slug or slug in {"characters"}:
            continue
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if not label:
            continue
        display = re.sub(r"\bNEW\b", "", label, flags=re.I).strip()
        display = re.sub(r"\bZZZ\b", "", display).strip()
        if not _is_hsr_entry(label):
            continue
        alias: list[str] = []
        if "ZZZ" in label.upper():
            alias.append(slug)
        # Slugs disambiguate alternate forms (March 7th / Trailblazer) better
        # than display names, which omit or reuse the base name.
        nanoka_id = nanoka.character_id(slug=slug) if nanoka else None
        if nanoka_id is None and nanoka is not None:
            nanoka_id = nanoka.character_id(name=display)
        entries.setdefault(
            slug,
            RosterEntry(slug=slug, name=display, url=f"{PRYDWEN_BASE}/{slug}", nanoka_id=nanoka_id, aliases=alias),
        )
    return sorted(entries.values(), key=lambda item: (normalize_name(item.name), item.slug))


def write_raw_urls(entries: list[RosterEntry], path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_index": PRYDWEN_CHARACTERS_URL,
        "characters": [entry.to_dict() for entry in entries],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_raw_urls(path: Path) -> list[RosterEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload if isinstance(payload, list) else payload.get("characters", [])
    return [
        RosterEntry(
            slug=item["slug"],
            name=item["name"],
            url=item["url"],
            nanoka_id=item.get("nanoka_id"),
            aliases=list(item.get("aliases") or []),
        )
        for item in entries
    ]