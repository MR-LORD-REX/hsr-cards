from __future__ import annotations

from typing import Final

#: Data version used when the caller does not pin one. ``update_assets()``
#: resolves ``manifest.json`` and replaces this with the newest published build.
DEFAULT_STATIC_VERSION = "4.7.51"

#: The stable game build (what the live site defaults to).
DEFAULT_LIVE_VERSION = "4.7"

DEFAULT_BASE_URL = "https://static.nanoka.cc/hsr"
DEFAULT_ASSET_BASE_URL = "https://static.nanoka.cc/assets/hsr"
DEFAULT_MANIFEST_URL = "https://static.nanoka.cc/manifest.json"
DEFAULT_GAME_KEY = "hsr"
DEFAULT_CACHE_DIR = ".nanoka_cache"
DEFAULT_CONCURRENCY = 16

#: Supported locales. The CDN publishes exactly these four folders for HSR.
SUPPORTED_LOCALES: Final[tuple[str, ...]] = ("en", "zh", "ja", "ko")

#: Human names for the four endgame calendars exposed by Nanoka.
MODE_LABELS: Final[dict[str, str]] = {
    "maze": "Forgotten Hall / Memory of Chaos",
    "maze_extra": "Pure Fiction",
    "maze_boss": "Apocalyptic Shadow",
    "maze_peak": "Anomaly Arbitration",
}

#: Maps user-facing aliases onto the four canonical mode identifiers.
GAME_MODE_ALIASES: Final[dict[str, str]] = {
    "maze": "maze",
    "moc": "maze",
    "memory of chaos": "maze",
    "memory-of-chaos": "maze",
    "forgotten hall": "maze",
    "forgotten-hall": "maze",
    "fh": "maze",
    "maze_extra": "maze_extra",
    "extra": "maze_extra",
    "pf": "maze_extra",
    "pure fiction": "maze_extra",
    "pure-fiction": "maze_extra",
    "purefiction": "maze_extra",
    "maze_boss": "maze_boss",
    "boss": "maze_boss",
    "as": "maze_boss",
    "apocalyptic shadow": "maze_boss",
    "apocalyptic-shadow": "maze_boss",
    "apocalyptic": "maze_boss",
    "shadow": "maze_boss",
    "maze_peak": "maze_peak",
    "peak": "maze_peak",
    "anomaly": "maze_peak",
    "arbitration": "maze_peak",
    "anomaly arbitration": "maze_peak",
    "anomaly-arbitration": "maze_peak",
    "aa": "maze_peak",
}

#: Catalog filename per mode, and the localized detail folder used by the site.
MODE_CATALOGS: Final[dict[str, str]] = {
    "maze": "maze.json",
    "maze_extra": "maze_extra.json",
    "maze_boss": "maze_boss.json",
    "maze_peak": "maze_peak.json",
}

MODE_DETAIL_FOLDERS: Final[dict[str, str]] = {
    "maze": "maze",
    "maze_extra": "story",
    "maze_boss": "boss",
    "maze_peak": "peak",
}

#: Map path codenames (used by the CDN) to the community-facing path names.
PATH_ALIASES: Final[dict[str, str]] = {
    "knight": "preservation", #correct
    "rogue": "hunt", #correct
    "mage": "erudition",  #correct
    "shaman": "harmony", #fixed
    "warlock": "nihility", #correct
    "warrior": "destruction", #correct
    "memory": "remembrance", #correct
    "elation": "elation", #correct
    "priest" : "abundance" #added
}

ELEMENTS: Final[tuple[str, ...]] = (
    "physical",
    "fire",
    "ice",
    "thunder",
    "wind",
    "quantum",
    "imaginary",
)

RARITY_MAP: Final[dict[str, int]] = {
    "CombatPowerAvatarRarityType5": 5,
    "CombatPowerAvatarRarityType4": 4,
    "CombatPowerLightconeRarity5": 5,
    "CombatPowerLightconeRarity4": 4,
    "CombatPowerLightconeRarity3": 3,
    "SuperRare": 5,
    "VeryRare": 4,
    "Rare": 3,
    "NotNormal": 2,
    "Normal": 1,
}