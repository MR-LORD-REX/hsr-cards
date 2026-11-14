"""Prydwen HSR tier-list parser.

The page embeds the MOC, PF, and AS rankings, so every mode can be read without
a browser. Prydwen uses Cloudflare; requests use ``cloudscraper``
inside ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urljoin

TIER_LIST_URL = "https://www.prydwen.gg/star-rail/tier-list"
GameMode = Literal["MOC", "PF", "AS"]
_MODE_INFO = {
    "MOC": ("Memory of Chaos", "moc"),
    "PF": ("Pure Fiction", "pure"),
    "AS": ("Apocalyptic Shadow", "apo"),
}
# Prydwen stores ratings numerically; these are the labels used by its UI.
_RATING_TIERS = {
    11: ("T0", "t0", "apex"), 10: ("T0.5", "t05", "apex"),
    9: ("T1", "t1", "meta"), 8: ("T1.5", "t15", "meta"),
    7: ("T2", "t2", "meta"), 6: ("T3", "t3", "niche"),
    5: ("T4", "t4", "niche"), 4: ("T5", "t5", "forgotten"),
}
_CATEGORY_ROLES = {
    "DPS": "dps", "Specialist": "debuffer", "Support DPS": "debuffer",
    "Amplifier": "support", "Sustain": "sustain",
}

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

_ROLE_NAMES = {
    "dps": "DPS",
    "debuffer": "Support DPS",
    "support": "Amplifier",
    "sustain": "Sustain",
}

_GROUP_NAMES = {
    "apex": "Apex Characters",
    "meta": "Meta Characters",
    "niche": "Off-Meta Characters",
    "forgotten": "The Forgotten Ones",
}

_ELEMENT_CLASSES = {
    "physical",
    "fire",
    "ice",
    "lightning",
    "wind",
    "quantum",
    "imaginary",
}


@dataclass(frozen=True, slots=True)
class RoleHeader:
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class TierCharacter:
    name: str
    slug: str
    icon_url: str
    element: str
    rarity: int
    eidolon: str
    tags: list[str]
    marks: list[str]

    @property
    def url(self) -> str:
        return f"https://www.prydwen.gg/star-rail/characters/{self.slug}"


@dataclass(frozen=True, slots=True)
class TierRole:
    key: str
    name: str
    characters: list[TierCharacter]


@dataclass(frozen=True, slots=True)
class Tier:
    name: str
    key: str
    roles: list[TierRole]


@dataclass(frozen=True, slots=True)
class TierGroup:
    key: str
    name: str
    tiers: list[Tier]


@dataclass(frozen=True, slots=True)
class TierListData:
    mode: str
    mode_key: str
    updated: str | None
    roles: list[RoleHeader]
    groups: list[TierGroup]
    source: str = TIER_LIST_URL

    @property
    def tiers(self) -> list[Tier]:
        return [tier for group in self.groups for tier in group.tiers]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _Node:
    __slots__ = ("tag", "attrs", "children", "parts")

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Node] = []
        self.parts: list[str | _Node] = []

    @property
    def classes(self) -> list[str]:
        return (_attr(self.attrs, "class")).split()

    def _text(self) -> str:
        return "".join(part if isinstance(part, str) else part._text() for part in self.parts)

    def text(self) -> str:
        return _clean_text(self._text())


def _attr(attrs: list[tuple[str, str | None]], name: str) -> str:
    for key, value in attrs:
        if key == name:
            return value or ""
    return ""


def _has_class(node: _Node | None, name: str) -> bool:
    return node is not None and name in node.classes


def _find_all(
    node: _Node | None,
    *,
    tag: str | None = None,
    class_name: str | None = None,
) -> list[_Node]:
    if node is None:
        return []
    found: list[_Node] = []
    for child in node.children:
        if (tag is None or child.tag == tag) and (
            class_name is None or class_name in child.classes
        ):
            found.append(child)
        found.extend(_find_all(child, tag=tag, class_name=class_name))
    return found


def _find_first(
    node: _Node | None,
    *,
    tag: str | None = None,
    class_name: str | None = None,
) -> _Node | None:
    if node is None:
        return None
    for child in node.children:
        if (tag is None or child.tag == tag) and (
            class_name is None or class_name in child.classes
        ):
            return child
        found = _find_first(child, tag=tag, class_name=class_name)
        if found is not None:
            return found
    return None


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", [])
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.lower(), attrs)
        self._stack[-1].children.append(node)
        self._stack[-1].parts.append(node)
        if tag.lower() not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.lower(), attrs)
        self._stack[-1].children.append(node)
        self._stack[-1].parts.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].parts.append(data)


def _parse_dom(html: str) -> _Node:
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    return parser.root


def _role_headers(container: _Node) -> list[RoleHeader]:
    header = _find_first(container, class_name="custom-tier-header")
    headers: list[RoleHeader] = []
    for node in _find_all(header, class_name="custom-header"):
        key = next((name for name in node.classes if name in _ROLE_NAMES), "")
        if not key:
            continue
        headers.append(RoleHeader(key=key, name=_ROLE_NAMES.get(key, node.text() or key)))
    return headers


def _group_key(node: _Node | None) -> str:
    if node is None:
        return "meta"
    for name in node.classes:
        if name in _GROUP_NAMES:
            return name
    return "meta"


def _tier_key(node: _Node) -> str:
    for name in node.classes:
        if name.startswith("tier-"):
            return name.removeprefix("tier-")
    return ""


def _parse_character(card: _Node, source: str) -> TierCharacter | None:
    link = _find_first(card, tag="a")
    avatar = _find_first(card, class_name="avatar")
    icon = _find_first(avatar, tag="img") or _find_first(card, tag="img")
    if icon is None:
        return None

    name = _attr(icon.attrs, "alt").strip()
    slug = ""
    if link is not None:
        href = _attr(link.attrs, "href").rstrip("/")
        slug = href.rsplit("/", 1)[-1]
    if not name:
        name = slug.replace("-", " ").title()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")

    rarity = 0
    if avatar is not None:
        for class_name in avatar.classes:
            if class_name.startswith("rarity-"):
                try:
                    rarity = int(class_name.removeprefix("rarity-"))
                except ValueError:
                    pass
                break

    element = ""
    element_node = _find_first(card, class_name="element")
    if element_node is not None:
        for class_name in element_node.classes:
            if class_name.casefold() in _ELEMENT_CLASSES:
                element = class_name
                break
        if not element:
            element_img = _find_first(element_node, tag="img")
            if element_img is not None:
                element = _attr(element_img.attrs, "alt")

    eidolon = _find_first(card, class_name="eidolon")
    eidolon_text = eidolon.text() if eidolon is not None else ""

    tags = []
    for node in _find_all(card, class_name="single-tag"):
        tag = re.sub(r"[\s,]+$", "", node.text())
        if tag:
            tags.append(tag)

    marks = []
    for node in _find_all(card, class_name="tier-marks"):
        for class_name in node.classes:
            if class_name not in {"floating-element", "tier-marks"}:
                marks.append(class_name)

    icon_src = _attr(icon.attrs, "src").strip()
    if not icon_src or icon_src.startswith("data:"):
        icon_src = _attr(icon.attrs, "data-src").strip()
    if not icon_src:
        srcset = _attr(icon.attrs, "srcset") or _attr(icon.attrs, "data-srcset")
        icon_src = srcset.split(",")[0].strip().split(" ")[0]

    return TierCharacter(
        name=name,
        slug=slug,
        icon_url=urljoin(source, icon_src) if icon_src else "",
        element=element,
        rarity=rarity,
        eidolon=eidolon_text,
        tags=tags,
        marks=marks,
    )


def _parse_tier(tier_node: _Node, headers: list[RoleHeader], source: str) -> Tier:
    rating = _find_first(tier_node, class_name="tier-rating")
    name = rating.text() if rating is not None else ""
    values: dict[str, TierRole] = {}
    container = _find_first(tier_node, class_name="custom-tier-container")
    if container is not None:
        for role_node in container.children:
            if "custom-tier-burst" not in role_node.classes:
                continue
            key = next(
                (class_name for class_name in role_node.classes if class_name in _ROLE_NAMES),
                "dps",
            )
            characters = [
                character
                for card in _find_all(role_node, class_name="avatar-card")
                if (character := _parse_character(card, source)) is not None
            ]
            values[key] = TierRole(
                key=key,
                name=_ROLE_NAMES.get(key, key.title()),
                characters=characters,
            )

    if headers:
        roles = [values.get(header.key, TierRole(header.key, header.name, [])) for header in headers]
    else:
        roles = list(values.values())

    return Tier(name=name or _tier_key(tier_node).upper(), key=_tier_key(tier_node), roles=roles)


def _parse_mode(root: _Node) -> tuple[str, str]:
    switcher = _find_first(root, class_name="tier-list-switcher")
    options = _find_all(switcher, class_name="option")
    selected = next((option for option in options if "selected" in option.classes), None)
    if selected is None and options:
        selected = options[0]
    if selected is None:
        return "Memory of Chaos", "moc"
    key = next((name for name in selected.classes if name not in {"option", "selected"}), "")
    return selected.text() or "Memory of Chaos", key or "moc"


def _parse_updated(html: str) -> str | None:
    match = re.search(
        r"Last updated:\s*(?:<!--\s*-->)?\s*<strong\b[^>]*>(.*?)</strong>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    return _clean_text(unescape(re.sub(r"<[^>]+>", "", match.group(1)))) if match else None


def _normalize_mode(game_mode: str) -> str:
    mode = game_mode.upper() if isinstance(game_mode, str) else ""
    if mode not in _MODE_INFO:
        raise ValueError("game_mode must be one of MOC, PF, AS")
    return mode


def _hydrated_ratings(root: _Node) -> dict[str, Any] | None:
    """Read JSON carried by Next.js without executing any page JavaScript.

    Flight data can span multiple script tags, so decode the transport chunks
    first, join them in document order, then read the tier-list component props.
    """
    decoder = json.JSONDecoder()
    chunks: list[str] = []
    for script in _find_all(root, tag="script"):
        content = script._text()
        for match in re.finditer(r"self\.__next_f\.push\(", content):
            try:
                chunk, _ = decoder.raw_decode(content[match.end():])
            except ValueError:
                continue
            if (isinstance(chunk, list) and len(chunk) > 1
                    and chunk[0] == 1 and isinstance(chunk[1], str)):
                chunks.append(chunk[1])
    stream = "".join(chunks)
    for match in re.finditer(r'\{\s*"characters"\s*:', stream):
        try:
            payload, _ = decoder.raw_decode(stream[match.start():])
        except ValueError:
            continue
        if (isinstance(payload, dict) and isinstance(payload.get("characters"), list)
                and isinstance(payload.get("ratings"), list)):
            return payload
    return None


def _parse_ratings(
    payload: dict[str, Any], game_mode: str, updated: str | None, source: str,
) -> TierListData:
    mode_name, mode_key = _MODE_INFO[game_mode]
    headers = [RoleHeader(key, name) for key, name in _ROLE_NAMES.items()]
    characters = {character["slug"]: character for character in payload["characters"]}
    buckets: dict[int, dict[str, list[TierCharacter]]] = {
        rating: {header.key: [] for header in headers} for rating in _RATING_TIERS
    }
    for entry in payload["ratings"]:
        if entry.get("show") is False:
            continue
        rating = entry.get(f"{mode_key}_rating")
        if rating is None or rating == 0:
            continue  # Not ranked in this mode.
        if rating not in buckets:
            raise ValueError(f"Unsupported Prydwen rating {rating!r} for {game_mode}")
        role = _CATEGORY_ROLES.get(entry.get("category", ""))
        if role is None:
            raise ValueError(f"Unknown Prydwen role: {entry.get('category')!r}")
        slug = entry["slug"]
        if slug not in characters:
            raise ValueError(f"Prydwen character metadata not found: {slug}")
        character = characters[slug]
        rarity = int(entry.get("rarity") or character.get("rarity") or 0)
        marks = [
            "watchlist" if mark.strip() == "watch" else mark.strip()
            for mark in (entry.get(f"{mode_key}_marks") or "").split(",") if mark.strip()
        ]
        icon_src = character.get("smallImage") or ""
        buckets[rating][role].append(TierCharacter(
            name=character.get("name") or entry.get("name") or slug,
            slug=slug,
            icon_url=urljoin(source, icon_src) if icon_src else "",
            element=entry.get("element") or character.get("element") or "",
            rarity=rarity,
            eidolon="E6" if rarity == 4 or character.get("isSpecialRating") else "E0",
            tags=[tag.strip() for tag in (entry.get(f"{mode_key}_tags") or "").split(",") if tag.strip()],
            marks=marks,
        ))
    if not any(characters for roles in buckets.values() for characters in roles.values()):
        raise ValueError(f"Prydwen tier list contains no characters for {game_mode}")
    groups = [TierGroup(key, name, []) for key, name in _GROUP_NAMES.items()]
    group_map = {group.key: group for group in groups}
    for rating, (name, key, group_key) in _RATING_TIERS.items():
        roles = [
            TierRole(header.key, header.name, sorted(buckets[rating][header.key], key=lambda c: c.slug))
            for header in headers
        ]
        group_map[group_key].tiers.append(Tier(name, key, roles))
    return TierListData(mode_name, mode_key, updated, headers, groups, source)

def parse_tier_list(
    html: str, *, game_mode: GameMode = "MOC", source: str = TIER_LIST_URL,
) -> TierListData:
    """Parse MOC, PF, or AS rankings from Prydwen's HTML and embedded data.

    Plain HTML without embedded ratings is supported only when its visible
    tier list matches the requested mode; it never substitutes another mode.
    """
    selected_mode = _normalize_mode(game_mode)
    root = _parse_dom(html)
    payload = _hydrated_ratings(root)
    if payload is not None:
        return _parse_ratings(payload, selected_mode, _parse_updated(html), source)
    mode, mode_key = _parse_mode(root)
    if mode_key != _MODE_INFO[selected_mode][1]:
        raise ValueError(f"Prydwen page has no embedded ratings for {selected_mode}")
    container = _find_first(root, class_name="custom-tier-list-hsr")
    if container is None:
        raise ValueError("Prydwen tier-list container not found")

    headers = _role_headers(container)
    groups: list[TierGroup] = []
    for child in container.children:
        if "meta-line" in child.classes:
            heading = _find_first(child, tag="h5")
            current_key = _group_key(heading)
            groups.append(
                TierGroup(
                    key=current_key,
                    name=_GROUP_NAMES.get(current_key, heading.text() if heading else current_key),
                    tiers=[],
                )
            )
        elif "custom-tier" in child.classes:
            if not groups:
                groups.append(TierGroup(key="meta", name=_GROUP_NAMES["meta"], tiers=[]))
            groups[-1].tiers.append(_parse_tier(child, headers, source))

    if not any(role.characters for group in groups for tier in group.tiers for role in tier.roles):
        raise ValueError("Prydwen tier list contains no characters")
    if not headers:
        headers = [RoleHeader(role.key, role.name) for role in next(tier for group in groups for tier in group.tiers).roles]

    return TierListData(
        mode=mode,
        mode_key=mode_key,
        updated=_parse_updated(html),
        roles=headers,
        groups=groups,
        source=source,
    )


def _fetch_html(url: str, timeout: float, proxy: str | None = None) -> str:
    try:
        import cloudscraper
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("cloudscraper is required to fetch Prydwen pages") from exc

    with cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    ) as scraper:
        if proxy:
            scraper.proxies.update({"http": proxy, "https": proxy})
        response = scraper.get(url, headers=_HEADERS, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"Prydwen returned {response.status_code} for {url}")
        return response.text


async def fetch_tier_list(
    url: str = TIER_LIST_URL,
    *,
    game_mode: GameMode = "MOC",
    timeout: float = 30.0,
    proxy: str | None = None,
) -> TierListData:
    """Fetch and parse the requested MOC, PF, or AS tier list."""
    _normalize_mode(game_mode)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    html = await asyncio.to_thread(_fetch_html, url, timeout, proxy)
    return parse_tier_list(html, game_mode=game_mode, source=url)


__all__ = [
    "TIER_LIST_URL",
    "GameMode",
    "RoleHeader",
    "Tier",
    "TierCharacter",
    "TierGroup",
    "TierListData",
    "TierRole",
    "fetch_tier_list",
    "parse_tier_list",
]