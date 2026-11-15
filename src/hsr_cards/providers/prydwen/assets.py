"""Read-only Nanoka catalog index used to rewrite Prydwen names to local art.

Nanoka is the asset authority. This module never downloads files: it reads the
existing ``hsr_cards`` cache and emits paths relative to its ``assets/hsr`` root
so a generated build can be rendered later without Prydwen URLs or network I/O.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import AssetRef

DEFAULT_NANOKA_VERSION = "4.7.51"
from .paths import default_nanoka_cache


_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8"}

# Prydwen display path -> Nanoka pathicon codename.
_PATH_ALIASES = {
    "preservation": "knight",
    "hunt": "rogue",
    "the hunt": "rogue",
    "erudition": "mage",
    "harmony": "shaman",
    "nihility": "warlock",
    "destruction": "warrior",
    "remembrance": "memory",
    "elation": "elation",
    "abundance": "priest",
}

# Prydwen / game display element -> Nanoka element filename.
_ELEMENT_ALIASES = {
    "physical": "physical",
    "fire": "fire",
    "ice": "ice",
    "lightning": "thunder",
    "thunder": "thunder",
    "wind": "wind",
    "quantum": "quantum",
    "imaginary": "imaginary",
}

# Prydwen uses many aliases for the same stat icon. Keep both the display
# labels and the game's icon stems so cards never fall back to text-only rows.
_STAT_ICONS = {
    "hp": "IconMaxHP",
    "max hp": "IconMaxHP",
    "atk": "IconAttack",
    "attack": "IconAttack",
    "def": "IconDefence",
    "defence": "IconDefence",
    "defense": "IconDefence",
    "speed": "IconSpeed",
    "spd": "IconSpeed",
    "crit rate": "IconCriticalChance",
    "crit dmg": "IconCriticalDamage",
    "crit damage": "IconCriticalDamage",
    "break effect": "IconBreakUp",
    "effect hit rate": "IconStatusProbability",
    "effect hit rating": "IconStatusProbability",
    "ehr": "IconStatusProbability",
    "effect res": "IconStatusResistance",
    "effect resistance": "IconStatusResistance",
    "energy regen": "IconEnergyRecovery",
    "er": "IconEnergyRecovery",
    "energy regen rate": "IconEnergyRecovery",
    "energy regeneration rate": "IconEnergyRecovery",
    "energy regeneration": "IconEnergyRecovery",
    "err": "IconEnergyRecovery",
    "outgoing healing boost": "IconHealRatio",
    "outgoing healing": "IconHealRatio",
    "healing boost": "IconHealRatio",
    "healing bonus": "IconHealRatio",
}

# Skill priority labels map to Nanoka's per-character skill icon files.
_SKILL_ICON_STEMS = {
    "basic": "Normal",
    "basic atk": "Normal",
    "skill": "BP",
    "ultimate": "Ultra",
    "ult": "Ultra",
    "talent": "Passive",
    "technique": "Maze",
    "memosprite skill": "Servant01",
    "memosprite talent": "ServantPassive",
    "servant": "Servant01",
    "servant passive": "ServantPassive",
    "elation skill": "Elation",
    "aeon": "Aeon",
}

# Major traces use SkillTree artwork. RankN artwork belongs to Eidolons.
_TRACE_ICON_STEMS = {"a2": "SkillTree1", "a4": "SkillTree2", "a6": "SkillTree3"}

# Prydwen URL identities can disambiguate repeated English display names.
# IDs are verified against rawUrls.json and the local character catalog.
_CHARACTER_SLUG_IDS = {
    "march 7th": 1001,
    "imbibitor lunae": 1213,
    "blade mortenax": 1507,
}

# Names that are not direct Nanoka ``en`` strings, or that are ambiguous in the
# catalog. Explicit IDs are safer than fuzzy matching for card-ready data.
_CHARACTER_ID_ALIASES = {
    "aha": 1511,
    "aeon aha": 1511,
    "march 7th the hunt": 1224,
    "march 7th swordmaster": 1224,
    "march 7th evernight": 1413,
    "tingyun fugue": 1225,
    "trailblazer destruction": 8001,
    "trailblazer preservation": 8003,
    "trailblazer harmony": 8005,
    "trailblazer remembrance": 8007,
    "trailblazer elation": 8009,
    "robin summeretto": 1512,
    "aventurine waveflair": 1513,
    "silver wolf lv 999": 1506,
}

_RARITY_RE = re.compile(r"rarity-(\d)")
_SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def normalize_name(value: str) -> str:
    """Normalize source names to ASCII comparison keys, including Roman numeral aliases."""
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = text.replace("★", " ").replace("•", " ").replace("·", " ")
    text = text.replace("'", "'").replace("`", "'")
    text = re.sub(r"<unbreak>.*?</unbreak>", " ", text)
    text = re.sub(r"\blv\.?\s*(\d+)\b", r"lv\1", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [_ROMAN.get(word, word) for word in text.split()]
    return " ".join(words)


def clean_text(value: str | None) -> str:
    """Remove markup and collapse whitespace; missing values become an empty string."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", value)
    text = text.replace("\\n", " ").replace("\xa0", " ")
    return " ".join(text.split())


def parse_rarity(value: str | None) -> int | None:
    """Read a source rarity class or Nanoka rarity label; return None when absent."""
    if not value:
        return None
    match = re.search(r"rarity-(\d)", value)
    if match:
        return int(match.group(1))
    match = re.search(r"RarityType(\d)", value)
    return int(match.group(1)) if match else None


def parse_superimposition(value: str | None) -> int | None:
    """Read S1-S5 source notation case-insensitively, or return None if unspecified."""
    if not value:
        return None
    match = re.search(r"\(S(\d)\)", value, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"\bS(\d)\b", value, re.I)
    return int(match.group(1)) if match else None


def parse_score(value: str | None) -> tuple[float | None, str | None]:
    """Return the first percentage and original normalized score text, preserving qualifiers."""
    if not value:
        return None, None
    text = " ".join(value.split())
    match = _SCORE_RE.search(text)
    if match:
        return float(match.group(1)), text
    return None, text


def _asset(ref: str, relative_path: str) -> AssetRef:
    return AssetRef(ref=ref, relative_path=relative_path, local_name=Path(relative_path).name, source_url=None)


def _stat_key(value: str) -> str:
    text = clean_text(value).casefold()
    text = text.replace("%", "").replace("dmg", "damage")
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class NanokaIndex:
    """Read existing English Nanoka catalogs for one version without downloading assets.

    cache_dir defaults to a runtime-discovered local cache. Missing catalogs remain
    empty; ambiguous names remain unresolved rather than selecting an arbitrary form."""
    cache_dir: Path = field(default_factory=default_nanoka_cache)
    version: str = DEFAULT_NANOKA_VERSION
    characters: dict[int, dict[str, Any]] = field(default_factory=dict)
    light_cones: dict[int, dict[str, Any]] = field(default_factory=dict)
    relic_sets: dict[int, dict[str, Any]] = field(default_factory=dict)
    items: dict[int, dict[str, Any]] = field(default_factory=dict)
    _character_by_name: dict[str, list[int]] = field(default_factory=dict)
    _cone_by_name: dict[str, list[int]] = field(default_factory=dict)
    _relic_by_name: dict[str, list[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        data_dir = self.cache_dir / self.version / "en" / "data"
        self.characters = self._load(data_dir / "character.json")
        self.light_cones = self._load(data_dir / "lightcone.json")
        self.relic_sets = self._load(data_dir / "relicset.json")
        self.items = self._load_items(data_dir / "item.json")
        self._character_by_name = self._name_map(self.characters)
        self._cone_by_name = self._name_map(self.light_cones)
        self._relic_by_name = self._name_map(self.relic_sets)

    @staticmethod
    def _load(path: Path) -> dict[int, dict[str, Any]]:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        result: dict[int, dict[str, Any]] = {}
        for key, value in payload.items():
            if str(key).isdigit() and isinstance(value, dict):
                result[int(key)] = {"id": int(key), **value}
        return result

    @staticmethod
    def _load_items(path: Path) -> dict[int, dict[str, Any]]:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        result: dict[int, dict[str, Any]] = {}
        for key, value in payload.items():
            if str(key).isdigit() and isinstance(value, dict):
                result[int(key)] = {"id": int(key), **value}
        return result

    @staticmethod
    def _name_map(catalog: dict[int, dict[str, Any]]) -> dict[str, list[int]]:
        result: dict[str, list[int]] = {}
        for identifier, record in catalog.items():
            for key in ("en", "zh", "ja", "ko"):
                name = record.get(key)
                if not isinstance(name, str) or not name:
                    continue
                normalized = normalize_name(clean_text(name))
                if normalized:
                    result.setdefault(normalized, []).append(identifier)
                raw_normalized = normalize_name(name)
                if raw_normalized and raw_normalized != normalized:
                    result.setdefault(raw_normalized, []).append(identifier)
        return result

    @property
    def available(self) -> bool:
        """Report whether at least one character, light-cone, or relic catalog was loaded."""
        return bool(self.characters or self.light_cones or self.relic_sets)

    def character(self, identifier: str | int | None = None, name: str | None = None) -> dict[str, Any] | None:
        """Return a character catalog row by numeric ID or unambiguous fallback name, otherwise None."""
        if identifier is not None and str(identifier).isdigit():
            record = self.characters.get(int(identifier))
            if record:
                return record
        return self._lookup_character(name)

    def _lookup_character(self, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        key = normalize_name(name)
        explicit = _CHARACTER_ID_ALIASES.get(key)
        if explicit is not None:
            return self.characters.get(explicit)
        return self._lookup(self.characters, self._character_by_name, name)

    def _lookup(self, catalog: dict[int, dict[str, Any]], names: dict[str, list[int]], name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        # A name that identifies several forms is unresolved. Never choose the
        # first catalog row or discard level/form words to force a match.
        identifiers = set(names.get(normalize_name(name), []))
        if len(identifiers) == 1:
            return catalog[next(iter(identifiers))]
        return None

    def character_id(self, name: str | None = None, slug: str | None = None) -> int | None:
        """Resolve a Prydwen slug or unambiguous display name to a cached Nanoka ID, otherwise None."""
        record = self._slug_character(slug) if slug else self._lookup_character(name)
        return int(record["id"]) if record is not None else None

    def _slug_character(self, slug: str) -> dict[str, Any] | None:
        key = normalize_name(slug)
        explicit = _CHARACTER_SLUG_IDS.get(key, _CHARACTER_ID_ALIASES.get(key))
        if explicit is not None:
            return self.characters.get(explicit)
        matches = {
            identifier
            for identifier, record in self.characters.items()
            if key in {normalize_name(record.get("icon", "")), normalize_name(clean_text(record.get("en")))}
        }
        return self.characters[next(iter(matches))] if len(matches) == 1 else None

    def light_cone(self, name: str | None) -> dict[str, Any] | None:
        """Return an unambiguous cached light-cone row for name, otherwise None."""
        return self._lookup(self.light_cones, self._cone_by_name, name)

    def relic(self, name: str | None) -> dict[str, Any] | None:
        """Return an unambiguous cached relic-set row for name, otherwise None."""
        return self._lookup(self.relic_sets, self._relic_by_name, name)

    def light_cone_asset(self, record: dict[str, Any]) -> AssetRef:
        """Build a Nanoka medium-icon reference from a catalog row containing an ID."""
        identifier = int(record["id"])
        return _asset(f"lightcone:{identifier}", f"lightconemediumicon/{identifier}.webp")

    def relic_asset(self, record: dict[str, Any]) -> AssetRef:
        """Build a relic figure reference; raise ValueError if the catalog icon is missing."""
        icon = record.get("icon")
        if not isinstance(icon, str) or not icon:
            raise ValueError(f"relic {record.get('en')!r} has no Nanoka icon path")
        stem = Path(icon).stem
        return _asset(f"relic:{record['id']}", f"itemfigures/{stem}.webp")

    def item_asset(self, record: dict[str, Any]) -> AssetRef | None:
        """Build an item figure reference from its catalog icon, or return None when absent."""
        icon = record.get("item_figure_icon_path")
        if not isinstance(icon, str) or not icon:
            return None
        return _asset(f"item:{record['id']}", f"itemfigures/{Path(icon).stem}.webp")

    def element_asset(self, element: str | None) -> AssetRef | None:
        """Return an element icon reference for a known case-insensitive alias, otherwise None."""
        if not element:
            return None
        key = element.strip().casefold().replace("_", " ")
        filename = _ELEMENT_ALIASES.get(key)
        if filename is None:
            return None
        return _asset(f"element:{filename}", f"element/{filename}.webp")

    def path_asset(self, path: str | None) -> AssetRef | None:
        """Return a path icon reference for a known case-insensitive alias, otherwise None."""
        if not path:
            return None
        key = path.strip().casefold()
        codename = _PATH_ALIASES.get(key)
        if codename is None:
            return None
        semantic = key.replace("the ", "", 1)
        return _asset(f"path:{semantic}", f"pathicon/{codename}.webp")

    def character_icon(self, identifier: int) -> AssetRef:
        """Build the avatar-shop icon reference for a numeric Nanoka character ID."""
        return _asset(f"character:{identifier}", f"avatarshopicon/{identifier}.webp")

    def character_round_icon(self, identifier: int) -> AssetRef:
        """Build the round-avatar icon reference for a numeric Nanoka character ID."""
        return _asset(f"character_round:{identifier}", f"avatarroundicon/{identifier}.webp")

    def character_drawcard(self, identifier: int) -> AssetRef:
        """Build the drawcard reference for a numeric Nanoka character ID."""
        return _asset(f"character_drawcard:{identifier}", f"avatardrawcard/{identifier}.webp")

    def stat_asset(self, label: str | None, element: str | None = None) -> AssetRef | None:
        """Resolve a Prydwen stat label to a Nanoka glyph.

        Prydwen splits damage bonuses into labels such as ``Ice DMG``. Those use
        the element icons rather than the generic stat sheet because players
        recognise the elemental shape faster than a generic sword glyph.
        """
        if not label:
            return None
        key = _stat_key(label)
        stem = _STAT_ICONS.get(key)
        if stem is None:
            # Parenthetical qualifiers describe the target, not a new stat.
            # Only exact known labels before a balanced final qualifier match.
            unqualified = re.sub(r"\s+\([^()]*\)$", "", key)
            stem = _STAT_ICONS.get(unqualified)
        if stem is not None:
            return _asset(f"stat:{stem}", f"skillicons/{stem}.webp")
        # Elemental damage labels are explicit. CRIT damage and an unknown
        # percentage must never inherit the character's elemental or ATK icon.
        element_key = re.sub(r"\s+(?:damage|damage bonus|damage boost)$", "", key)
        filename = _ELEMENT_ALIASES.get(element_key)
        if filename and element_key != key:
            return _asset(f"stat:element:{filename}", f"element/{filename}.webp")
        if key in {"damage", "damage bonus", "damage boost"} and element:
            filename = _ELEMENT_ALIASES.get(element.casefold())
            if filename:
                return _asset(f"stat:element:{filename}", f"element/{filename}.webp")
        return None

    def skill_asset(self, identifier: int | None, label: str | None) -> AssetRef | None:
        """Resolve a skill label to an icon, inspecting local files for memosprite variants.

        Return None for unknown labels or nonunique memosprite artwork; never fetch files."""
        if identifier is None or not label:
            return None
        key = _stat_key(label)
        key = {
            "memo skill": "memosprite skill",
            "memo talent": "memosprite talent",
            "m.skill": "memosprite skill",
            "m.talent": "memosprite talent",
        }.get(key, key)
        stem = _SKILL_ICON_STEMS.get(key)
        if stem is None:
            return None
        if key in {"memosprite skill", "memosprite talent", "servant", "servant passive"}:
            # Nanoka stores memosprite skills under their own 1xxxx identity,
            # with distinct Servant / Servant01 / Servant03 stems. Resolve only
            # an existing unique file rather than inventing one for the owner.
            asset_dir = self.cache_dir / self.version / "en" / "assets"
            sprite_id = identifier + 10_000
            candidates = list((asset_dir / "skillicons").glob(f"SkillIcon_{sprite_id}_Servant*.webp"))
            passive = key in {"memosprite talent", "servant passive"}
            candidates = [p for p in candidates if ("Passive" in p.stem) == passive]
            if len(candidates) != 1:
                return None
            relative = candidates[0].relative_to(asset_dir).as_posix()
            return _asset(f"skill:{sprite_id}:{candidates[0].stem.split('_', 2)[-1]}", relative)
        relative = f"skillicons/SkillIcon_{identifier}_{stem}.webp"
        return _asset(f"skill:{identifier}:{stem}", relative)

    def trace_asset(self, identifier: int | None, label: str | None, index: int = 0) -> AssetRef | None:
        """Resolve explicit A2/A4/A6 trace labels to icons; ambiguous source order returns None."""
        if identifier is None or not label:
            return None
        key = label.casefold()
        for token, stem in _TRACE_ICON_STEMS.items():
            if re.search(rf"\b{token}\b", key):
                return _asset(f"trace:{identifier}:{stem}", f"skillicons/SkillIcon_{identifier}_{stem}.webp")
        # Source order alone cannot establish a major trace's identity.
        return None

    def match_character(self, display_name: str) -> tuple[int | None, str]:
        """Return a resolved ID and informative canonical name, preserving unresolved source names."""
        record = self._lookup_character(display_name)
        if record:
            canonical = clean_text(record.get("en"))
            # March's two forms share the same catalog name, and Trailblazer
            # uses a player placeholder. Preserve the informative source label.
            if not canonical or self._lookup_character(canonical) is None:
                canonical = display_name
            return int(record["id"]), canonical
        return None, display_name

    def asset_file(self, ref: AssetRef | dict[str, Any] | None) -> Path | None:
        """Return the cached local file for an AssetRef, if it exists."""
        if ref is None:
            return None
        relative = ref.get("relative_path") if isinstance(ref, dict) else ref.relative_path
        if not relative:
            return None
        asset_root = (self.cache_dir / self.version / "en" / "assets").resolve()
        candidate = (asset_root / relative).resolve()
        if not candidate.is_relative_to(asset_root):
            return None
        if candidate.is_file():
            return candidate
        # Optional property icons bundled in this project have proven game
        # identities and cover gaps in the existing Nanoka cache.
        if re.fullmatch(r"skillicons/Icon[A-Za-z0-9]+\.webp", relative):
            bundled = Path(__file__).resolve().parents[2] / "assets" / "prydwen_builds" / "property" / Path(relative).name
            if bundled.is_file():
                return bundled
        return None

    def has_asset(self, ref: AssetRef | dict[str, Any] | None) -> bool:
        """Report whether a referenced cache or bundled property-icon file exists locally."""
        return self.asset_file(ref) is not None


def catalog_paths(cache_dir: Path, version: str) -> tuple[Path, Path, Path]:
    """Return character, light-cone, and relic catalog paths for an English cached version."""
    data = Path(cache_dir) / version / "en" / "data"
    return data / "character.json", data / "lightcone.json", data / "relicset.json"

__all__ = [
    "DEFAULT_NANOKA_VERSION", "DEFAULT_NANOKA_CACHE", "NanokaIndex",
    "normalize_name", "clean_text", "parse_rarity", "parse_superimposition",
    "parse_score", "catalog_paths",
]


def __getattr__(name: str):
    """Resolve the legacy default-cache constant lazily at explicit attribute access.

    The cache location follows the caller's current working directory, matching
    default NanokaIndex construction without discovering filesystem paths at import.
    """
    if name == "DEFAULT_NANOKA_CACHE":
        return default_nanoka_cache()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
