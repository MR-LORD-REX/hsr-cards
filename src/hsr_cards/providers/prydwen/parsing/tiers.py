"""Convert server markup and embedded ratings into domain tier lists."""
from __future__ import annotations


import json

import re


from html import unescape


from typing import Any

from urllib.parse import urljoin


from ..models import TIER_LIST_URL, GameMode, RoleHeader, TierCharacter, TierRole, Tier, TierGroup, TierListData
from .tier_dom import _Node, _attr, _clean_text, _find_all, _find_first, _parse_dom


_MODE_INFO = {
    "MOC": ("Memory of Chaos", "moc"),
    "PF": ("Pure Fiction", "pure"),
    "AS": ("Apocalyptic Shadow", "apo"),
}


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
    game_mode defaults to MOC and accepts case-insensitive aliases. source is
    retained as provenance and resolves relative portraits. Returns TierListData;
    invalid modes, absent rankings, and malformed hydrated data raise ValueError.
    Performs no requests or filesystem operations.
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

