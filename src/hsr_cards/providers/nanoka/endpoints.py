from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    """One document on the Nanoka CDN.

    ``path`` is always relative to ``<base>/<version>/``. When ``localized`` is
    true the locale folder is inserted before the path.
    """

    path: str
    localized: bool = False
    required: bool = True
    cache_key: str | None = None

    def url(self, base_url: str, version: str, locale: str) -> str:
        """Build a CDN URL from base, version, and optional locale without making a request."""
        parts = [base_url.rstrip("/"), version]
        if self.localized:
            parts.append(locale)
        parts.append(self.path)
        return "/".join(parts)

    @property
    def key(self) -> str:
        """Return the explicit cache key, falling back to this endpoint relative path."""
        return self.cache_key or self.path


def localized_endpoint(path: str, *, required: bool = False) -> Endpoint:
    """Build a locale-prefixed Endpoint, optional unless required=True."""
    return Endpoint(path, localized=True, required=required)


#: Unlocalized catalogs (they carry the four-language names inline).
ROOT_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint("character.json"),
    Endpoint("lightcone.json"),
    Endpoint("relicset.json"),
    Endpoint("monster.json"),
    Endpoint("monstervalue.json", required=False),
    Endpoint("maze.json"),
    Endpoint("maze_extra.json"),
    Endpoint("maze_boss.json"),
    Endpoint("maze_peak.json"),
    Endpoint("InfiniteEliteGroup.json", required=False),
    Endpoint("HardLevelGroup.json", required=False),
    Endpoint("EliteGroup.json", required=False),
)

#: Catalogs that only exist inside a locale folder.
LOCALIZED_ROOT_ENDPOINTS: tuple[Endpoint, ...] = (
    localized_endpoint("item.json", required=True),
    localized_endpoint("item_all.json"),
    localized_endpoint("currency/item.json"),
    localized_endpoint("currency/role.json"),
    localized_endpoint("currency/trait.json"),
    localized_endpoint("currency/buff.json"),
    localized_endpoint("currency/augment.json"),
    localized_endpoint("achievement/achievement.json"),
)

#: Small season -> id maps used to enumerate endgame details.
VERSION_ENDPOINTS: tuple[Endpoint, ...] = (
    localized_endpoint("maze/version.json", required=True),
    localized_endpoint("peak/version.json", required=True),
)

#: Optional per-locale changelog (large, locale is the filename not folder).
DIFF_ENDPOINTS: tuple[Endpoint, ...] = (Endpoint("diff/{locale}.json", required=False),)

#: Folder used for each endgame detail on the CDN. Pure Fiction lives under
#: ``story`` and Apocalyptic Shadow under ``boss`` — those names are easy to
#: get wrong, so they are centralized here.
DETAIL_FOLDERS: dict[str, str] = {
    "character": "character",
    "lightcone": "lightcone",
    "relicset": "relicset",
    "monster": "monster",
    "maze": "maze",
    "maze_extra": "story",
    "maze_boss": "boss",
    "maze_peak": "peak",
}

#: Detail kinds that are enumerated from a catalog keyed by the same name.
CATALOG_DETAIL_KINDS: tuple[str, ...] = ("character", "lightcone", "relicset", "monster")

#: Detail kinds enumerated from a version map (season -> ids).
VERSION_DETAIL_KINDS: tuple[str, ...] = ("maze", "maze_extra", "maze_boss", "maze_peak")

#: Catalog files that are a dict keyed by id.
ID_CATALOGS: dict[str, str] = {
    "character": "character.json",
    "lightcone": "lightcone.json",
    "relicset": "relicset.json",
    "monster": "monster.json",
    "maze": "maze.json",
    "maze_extra": "maze_extra.json",
    "maze_boss": "maze_boss.json",
    "maze_peak": "maze_peak.json",
}


def detail_endpoint(kind: str, identifier: str | int) -> Endpoint:
    """Build a localized optional detail endpoint for a canonical kind and ID.

    Unknown kinds raise KeyError; constructing the endpoint performs no IO.
    """
    folder = DETAIL_FOLDERS[kind]
    return Endpoint(f"{folder}/{identifier}.json", localized=True, required=False,
                    cache_key=f"{folder}/{identifier}.json")


__all__ = [
    "Endpoint",
    "ROOT_ENDPOINTS",
    "LOCALIZED_ROOT_ENDPOINTS",
    "VERSION_ENDPOINTS",
    "DIFF_ENDPOINTS",
    "DETAIL_FOLDERS",
    "CATALOG_DETAIL_KINDS",
    "VERSION_DETAIL_KINDS",
    "ID_CATALOGS",
    "detail_endpoint",
]
