"""Catalog-derived aliases for Nanoka CDN asset paths."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..constants import PATH_ALIASES


RELIC_ICON_SPECS = {
    "relicslot:head": "relicfigures/IconRelicHead.webp",
    "relicslot:hands": "relicfigures/IconRelicHands.webp",
    "relicslot:body": "relicfigures/IconRelicBody.webp",
    "relicslot:feet": "relicfigures/IconRelicFoot.webp",
    "relicslot:planar_sphere": "relicfigures/IconRelicNeck.webp",
    "relicslot:link_rope": "relicfigures/IconRelicGoods.webp",
}

def collect_asset_specs(data_dir: Path) -> dict[str, str]:
    """Read cached catalogs/details and map asset aliases to CDN-relative paths.

    data_dir is the locale JSON directory. Return {} when it does not exist;
    malformed/unreadable individual documents are skipped. Built-in relic-slot
    aliases accompany inferred character, equipment, skill, element, and path
    aliases. This reads disk data and performs no network requests or writes.
    """
    if not data_dir.is_dir():
        return {}
    specs: dict[str, str] = {}
    character_catalog = _load_json_file(data_dir / "character.json")
    if isinstance(character_catalog, dict):
        for identifier, entry in character_catalog.items():
            if not str(identifier).isdigit():
                continue
            specs[f"character:{identifier}"] = f"avatarshopicon/{identifier}.webp"
            specs[f"avatar:{identifier}"] = f"avatarshopicon/{identifier}.webp"
            specs[f"character_round:{identifier}"] = f"avatarroundicon/{identifier}.webp"
            specs[f"character_drawcard:{identifier}"] = f"avatardrawcard/{identifier}.webp"
            if isinstance(entry, dict):
                element = entry.get("damageType")
                if isinstance(element, str):
                    add_element_spec(element, specs)
                path = entry.get("baseType")
                if isinstance(path, str):
                    add_path_spec(path, specs)
    lightcone_catalog = _load_json_file(data_dir / "lightcone.json")
    if isinstance(lightcone_catalog, dict):
        for identifier in lightcone_catalog:
            if str(identifier).isdigit():
                specs[f"lightcone:{identifier}"] = f"lightconemediumicon/{identifier}.webp"
    relic_catalog = _load_json_file(data_dir / "relicset.json")
    if isinstance(relic_catalog, dict):
        for identifier, entry in relic_catalog.items():
            if isinstance(entry, dict):
                icon = entry.get("icon")
                if isinstance(icon, str):
                    specs[f"relic:{identifier}"] = f"itemfigures/{Path(icon).stem}.webp"
    monster_catalog = _load_json_file(data_dir / "monster.json")
    if isinstance(monster_catalog, dict):
        for identifier, entry in monster_catalog.items():
            if not isinstance(entry, dict):
                continue
            icon = entry.get("icon")
            if isinstance(icon, str):
                specs[f"monster:{identifier}"] = f"monstermiddleicon/{Path(icon).stem}.webp"
            for weakness in entry.get("weak") or []:
                if isinstance(weakness, str):
                    add_element_spec(weakness, specs)
    for key, relative in RELIC_ICON_SPECS.items():
        specs[key] = relative
    for path in data_dir.rglob("*.json"):
        payload = _load_json_file(path)
        if payload is not None:
            _collect_from_payload(payload, specs)
    return specs

def _load_json_file(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def _collect_from_payload(payload: Any, specs: dict[str, str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if isinstance(value, str) and value:
                if lowered in {
                    "icon",
                    "icon_path",
                    "item_icon_path",
                    "item_figure_icon_path",
                    "item_currency_icon_path",
                    "image_path",
                    "max_sp_icon",
                    "item_avatar_icon_path",
                    "icon",
                }:
                    add_asset_spec(value, specs)
                elif lowered in {"damage_type", "damagetype", "damage_type_name"}:
                    add_element_spec(value, specs)
                elif lowered in {"base_type", "basetype"}:
                    add_path_spec(value, specs)
            _collect_from_payload(value, specs)
    elif isinstance(payload, list):
        for value in payload:
            _collect_from_payload(value, specs)

def add_asset_spec(value: str, specs: dict[str, str]) -> None:
    """Add CDN path and stem aliases to specs for a supported game asset path.

    Unknown bare names are ignored; mutate the supplied mapping without IO.
    """
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        return
    stem = Path(normalized).stem
    if not stem:
        return
    lower = normalized.lower()
    if lower.startswith("spriteoutput/monsterfigure/"):
        relative = f"monstermiddleicon/{stem}.webp"
    elif lower.startswith("spriteoutput/gridfight/equipment/"):
        relative = f"gridfight/equipment/{stem}.webp"
    elif lower.startswith("spriteoutput/gridfight/augment"):
        relative = f"gridfight/augmentbig/{stem}.webp"
    elif lower.startswith("spriteoutput/gridfight/portal/"):
        relative = f"gridfight/portal/{stem}.webp"
    elif lower.startswith(
        (
            "spriteoutput/itemicon/",
            "spriteoutput/itemfigures/",
            "spriteoutput/itemcurrency/",
        )
    ):
        relative = f"itemfigures/{stem}.webp"
    elif lower.startswith("spriteoutput/skillicon/") or stem.lower().startswith(("skillicon_", "icon")):
        relative = f"skillicons/{stem}.webp"
    elif "/" not in normalized and not lower.endswith((".webp", ".png", ".jpg", ".jpeg")):
        return
    else:
        relative = normalized.lstrip("/")
    specs[f"stem:{stem}"] = relative
    specs.setdefault(relative, relative)

def add_element_spec(name: str, specs: dict[str, str]) -> None:
    """Add a known element CDN alias to specs, ignoring unknown element names."""
    element = name.strip().lower()
    if element in {"physical", "fire", "ice", "thunder", "wind", "quantum", "imaginary"}:
        specs[f"element:{element}"] = f"element/{element}.webp"

def add_path_spec(name: str, specs: dict[str, str]) -> None:
    """Add path/codename CDN aliases to specs, ignoring unknown path names."""
    codename = name.strip().lower()
    if codename in PATH_ALIASES:
        relative = f"pathicon/{codename}.webp"
        specs[f"path:{codename}"] = relative
        specs[f"path:{PATH_ALIASES[codename]}"] = relative
    elif codename in PATH_ALIASES.values():
        specs[f"path:{codename}"] = f"pathicon/{codename}.webp"
