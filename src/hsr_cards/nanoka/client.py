from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Literal, TypeVar

from PIL import Image

from ..builds import find_builds, load_build_image
from .cache import NanokaCache, collect_asset_specs, default_cache_root, mode_key
from .constants import (
    DEFAULT_ASSET_BASE_URL,
    DEFAULT_BASE_URL,
    DEFAULT_CONCURRENCY,
    DEFAULT_STATIC_VERSION,
    MODE_DETAIL_FOLDERS,
    MODE_LABELS,
)
from .endpoints import DETAIL_FOLDERS
from .exceptions import NanokaAssetError, NanokaHTTPError, NanokaNotFoundError
from .http import AsyncHTTP
from .locales import DEFAULT_LOCALE, Locale
from .models import (
    NanokaVersions,
    AchievementSeries,
    CharacterDetail,
    CharacterSummary,
    CurrencyAugment,
    CurrencyBuff,
    CurrencyItem,
    CurrencyRole,
    CurrencyTrait,
    EndgameDetail,
    ItemSummary,
    LightConeDetail,
    LightConeSummary,
    MazeSchedule,
    MonsterDetail,
    MonsterStats,
    MonsterSummary,
    PeakDetail,
    PeakSchedule,
    RelicSetDetail,
    RelicSetSummary,
    StageEvent,
    StageLevel,
    as_utc,
    parse_datetime,
)

ModeName = Literal["maze", "maze_extra", "maze_boss", "maze_peak"]
T = TypeVar("T")


@dataclass
class BossEncounter:
    """Resolved endgame boss data for one stage (card-generator friendly)."""

    mode: str
    season: MazeSchedule
    stage: StageLevel | None = None
    detail: EndgameDetail | PeakDetail | None = None
    bosses: list[Monster] = field(default_factory=list)
    waves: list[StageEvent] = field(default_factory=list)
    monster_ids: list[int] = field(default_factory=list)
    locale: Locale = DEFAULT_LOCALE

    @property
    def mode_label(self) -> str:
        return MODE_LABELS[self.mode]

    @property
    def id(self) -> int:
        return self.season.id

    @property
    def name(self) -> str | None:
        return self.season.display_name()

    @property
    def version(self) -> str | None:
        return self.season.version

    @property
    def boss(self) -> "Monster | None":
        return self.bosses[0] if self.bosses else None

    def boss_names_for(
        self, locale: Locale | str | None = None, *, fallback: bool = True
    ) -> list[str]:
        loc = locale or self.locale
        return [
            boss.display_name(loc, fallback=fallback) or str(boss.id)
            for boss in self.bosses
        ]

    @property
    def boss_names(self) -> list[str]:
        return self.boss_names_for()

    @property
    def stage_name(self) -> str | None:
        return self.stage.name if self.stage else None

    @property
    def starts_at(self) -> datetime | None:
        if isinstance(self.detail, EndgameDetail):
            return self.detail.starts_at or self.season.begins_at
        return self.season.begins_at

    @property
    def ends_at(self) -> datetime | None:
        if isinstance(self.detail, EndgameDetail):
            return self.detail.ends_at or self.season.ends_at
        return self.season.ends_at

    def __repr__(self) -> str:
        names = ", ".join(self.boss_names) or "-"
        return f"BossEncounter(mode={self.mode!r}, season={self.season.id}, bosses=[{names}])"


@dataclass
class EndgameSeason:
    """A mode-specific schedule plus its detail document."""

    mode: str
    schedule: MazeSchedule
    detail: EndgameDetail | PeakDetail | None = None

    @property
    def id(self) -> int:
        return self.schedule.id

    @property
    def name(self) -> str | None:
        return self.schedule.display_name()

    @property
    def begins_at(self) -> datetime | None:
        return self.schedule.begins_at

    @property
    def ends_at(self) -> datetime | None:
        return self.schedule.ends_at

    @property
    def is_live(self) -> bool:
        return self.schedule.is_live if self.schedule.has_schedule else True

    @property
    def boss_ids(self) -> list[int]:
        return self.detail.boss_ids if self.detail else []

    @property
    def boss_names(self) -> list[str]:
        if isinstance(self.detail, PeakDetail):
            return [self.detail.boss_name] if self.detail.boss_name else []
        return []

    def __repr__(self) -> str:
        return f"EndgameSeason(mode={self.mode!r}, id={self.id}, name={self.name!r})"

class NanokaClient:
    """Async, cache-first client for static.nanoka.cc HSR data.

    The first data call downloads catalogs, localized detail documents, and
    the referenced icons into ``.nanoka_cache/``. Later calls read from disk.
    Call :meth:`update_assets` to revalidate and pull new releases.
    """

    def __init__(
        self,
        *,
        version: str | None = None,
        language: Locale | str = DEFAULT_LOCALE,
        cache_dir: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        asset_base_url: str = DEFAULT_ASSET_BASE_URL,
        proxy: str | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        include_assets: bool = True,
        auto_update: bool = False,
        concurrency: int = DEFAULT_CONCURRENCY,
    ):
        self.language = Locale.normalize(language)
        self.version = version or DEFAULT_STATIC_VERSION
        self.cache_dir = Path(cache_dir or default_cache_root()).expanduser().resolve()
        self.base_url = base_url.rstrip("/")
        self.asset_base_url = asset_base_url.rstrip("/")
        self.include_assets = include_assets
        self.auto_update = auto_update
        self._http = AsyncHTTP(
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            concurrency=concurrency,
        )
        self._cache = NanokaCache(
            cache_dir=self.cache_dir,
            version=version,
            locale=self.language,
            base_url=self.base_url,
            asset_base_url=self.asset_base_url,
            http=self._http,
            include_assets=include_assets,
            concurrency=concurrency,
            auto_update=auto_update,
        )

    @property
    def cache(self) -> NanokaCache:
        return self._cache

    @property
    def cache_path(self) -> Path:
        return self._cache.locale_dir

    async def __aenter__(self) -> "NanokaClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._cache.close()
        await self._http.close()

    async def initialize(self, *, force: bool = False) -> "NanokaClient":
        await self._cache.ensure(force=force)
        self.version = self._cache.version
        return self

    async def get_versions(self, *, refresh: bool = False) -> NanokaVersions:
        """Return the builds currently published by Nanoka.

        ``live_server`` is the stable game build (for example ``4.7``) and
        ``live_beta`` is the newest published patch build (for example
        ``4.7.51``). ``versions`` contains every selectable build.
        """
        return await self._cache.versions(refresh=refresh)


    async def update_assets(
        self,
        *,
        version: str | None = None,
        force: bool = False,
    ) -> "NanokaClient":
        """Revalidate/download one published build, or the active build.

        Passing ``version`` also switches the client to that build, so a
        subsequent card render reads the assets that were just refreshed.
        """
        target = str(version).strip() if version else None
        if target:
            published = await self.get_versions()
            if target not in published.versions:
                raise ValueError(
                    f"Unknown Nanoka version {target!r}; choose one of "
                    f"{', '.join(published.versions)}"
                )
            self.version = target
            self._cache.version = target
            self._cache._pinned_version = True
            self._cache._manifest = None
            self._cache._validators = {}
        await self._cache.update(force=force)
        self.version = self._cache.version
        return self

    async def clear_cache(self, *, version: str | None = None) -> None:
        """Clear one cached Nanoka build, or every build when omitted."""
        await self._cache.clear_version(version)

    async def _prepare(self, refresh: bool = False) -> None:
        if refresh:
            await self._cache.update()
        else:
            await self._cache.ensure()
        self.version = self._cache.version

    async def _catalog(self, filename: str, *, required: bool = True) -> dict[str, Any]:
        payload = await self._cache.load_json(filename, required=required)
        return payload if isinstance(payload, dict) else {}

    async def _detail(
        self,
        kind: str,
        identifier: int | str,
        *,
        required: bool = True,
        refresh: bool = False,
    ) -> dict[str, Any] | None:
        await self._prepare(refresh)
        folder = MODE_DETAIL_FOLDERS.get(kind, DETAIL_FOLDERS[kind])
        payload = await self._cache.load_json(f"{folder}/{identifier}.json", required=False)
        if payload is None:
            if required:
                raise NanokaNotFoundError(kind, identifier)
            return None
        return payload
    async def list_characters(
        self,
        *,
        element: str | None = None,
        path: str | None = None,
        rarity: int | None = None,
        released: bool | None = None,
        include_beta: bool = True,
        search: str | None = None,
        sort_by: str = "release",
        ascending: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> list[CharacterSummary]:
        await self._prepare(refresh)
        payload = await self._catalog("character.json")
        items = [
            CharacterSummary.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        items = _filter_characters(
            items,
            element=element,
            path=path,
            rarity=rarity,
            released=released,
            include_beta=include_beta,
            search=search,
            extra=filters,
        )
        return sort_characters(items, sort_by=sort_by, ascending=ascending, locale=self.language)

    async def get_character(
        self,
        identifier: int | str | None = None,
        *,
        name: str | None = None,
        element: str | None = None,
        path: str | None = None,
        rarity: int | None = None,
        released: bool | None = None,
        include_beta: bool = True,
        search: str | None = None,
        include_details: bool = True,
        sort_by: str = "release",
        ascending: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> Character | None:
        """Find by ID, name, or any catalog filter; returns the best match."""
        needle = name or search
        if identifier is not None and not str(identifier).isdigit() and needle is None:
            needle = str(identifier)
        items = await self.list_characters(
            element=element,
            path=path,
            rarity=rarity,
            released=released,
            include_beta=include_beta,
            search=needle,
            sort_by=sort_by,
            ascending=ascending,
            refresh=refresh,
            **filters,
        )
        if identifier is not None and str(identifier).isdigit():
            target = str(identifier)
            summary = next((item for item in items if str(item.id) == target), None)
        else:
            summary = items[0] if items else None
        if summary is None:
            return None
        detail = await self.get_character_detail(summary.id, refresh=False) if include_details else None
        return Character(summary=summary, detail=detail, locale=self.language)

    async def character_build(
        self,
        identifier: int | str | None = None,
        url: bool = False,
        *,
        detailed: bool = False,
        name: str | None = None,
        element: str | None = None,
        path: str | None = None,
        rarity: int | None = None,
        released: bool | None = None,
        include_beta: bool = True,
        search: str | None = None,
        build_dir: str | Path | None = None,
        **filters: Any,
    ) -> Image.Image | str | list[Image.Image] | list[str] | None:
        """Return one clean card, or the detailed summary and condition pages.

        ``url=True`` returns GitHub raw links. ``detailed=True`` always returns
        a list, with the summary first. Missing variants return ``None``.
        Local id/name lookups work without downloading the Nanoka catalog.
        """
        lookup = dict(name=name, search=search, build_dir=build_dir, detailed=detailed)
        catalog_filters = (
            any(value is not None for value in (element, path, rarity, released))
            or bool(filters) or not include_beta
        )
        records = [] if catalog_filters else find_builds(identifier, **lookup)
        if not records and not catalog_filters:
            other_variant = {**lookup, "detailed": not detailed}
            if find_builds(identifier, **other_variant):
                return None
        if not records:
            character = await self.get_character(
                identifier, name=name, element=element, path=path, rarity=rarity,
                released=released, include_beta=include_beta, search=search,
                include_details=False, **filters,
            )
            if character is None:
                return None
            records = find_builds(character.summary.id, build_dir=build_dir, detailed=detailed)
        if not records:
            return None
        if url:
            links = [record.raw_url for record in records]
            return links if detailed else links[0]
        images = [load_build_image(record) for record in records]
        if any(image is None for image in images):
            return None
        return images if detailed else images[0]

    async def get_character_detail(self, identifier: int | str, *, refresh: bool = False) -> CharacterDetail:
        payload = await self._detail("character", identifier, refresh=refresh)
        assert payload is not None
        return CharacterDetail.model_validate({"id": int(identifier), **payload})

    async def get_latest_character(
        self,
        *,
        include_beta: bool = True,
        include_details: bool = False,
        element: str | None = None,
        path: str | None = None,
        rarity: int | None = None,
        refresh: bool = False,
    ) -> Character | None:
        """Newest character.

        With ``include_beta=True``, unreleased entries win and the highest ID
        among them is returned (IDs increase with new reveals). Otherwise the
        newest released character by release timestamp.
        """
        items = await self.list_characters(
            element=element,
            path=path,
            rarity=rarity,
            released=None if include_beta else True,
            include_beta=include_beta,
            sort_by="id",
            ascending=True,
            refresh=refresh,
        )
        if not items:
            return None
        if include_beta:
            beta = [item for item in items if item.release is None]
            latest = max(beta, key=lambda item: item.id) if beta else max(
                items, key=lambda item: (item.release or 0, item.id)
            )
        else:
            latest = max(items, key=lambda item: (item.release or 0, item.id))
        detail = await self.get_character_detail(latest.id) if include_details else None
        return Character(summary=latest, detail=detail, locale=self.language)

    async def list_lightcones(
        self,
        *,
        path: str | None = None,
        rarity: int | None = None,
        search: str | None = None,
        sort_by: str = "id",
        ascending: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> list[LightConeSummary]:
        await self._prepare(refresh)
        payload = await self._catalog("lightcone.json")
        items = [
            LightConeSummary.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        items = filter_lightcones(items, path=path, rarity=rarity, search=search, language=self.language)
        items = apply_extra_filters(items, filters)
        return sort_lightcones(items, sort_by=sort_by, ascending=ascending, locale=self.language)

    async def get_lightcone(
        self,
        identifier: int | str | None = None,
        *,
        name: str | None = None,
        path: str | None = None,
        rarity: int | None = None,
        search: str | None = None,
        include_details: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> LightCone | None:
        needle = name or search
        if identifier is not None and not str(identifier).isdigit() and needle is None:
            needle = str(identifier)
        items = await self.list_lightcones(
            path=path,
            rarity=rarity,
            search=needle,
            refresh=refresh,
            **filters,
        )
        if identifier is not None and str(identifier).isdigit():
            summary = next((item for item in items if str(item.id) == str(identifier)), None)
        else:
            summary = items[0] if items else None
        if summary is None:
            return None
        detail = await self.get_lightcone_detail(summary.id) if include_details else None
        return LightCone(summary=summary, detail=detail, locale=self.language)

    async def get_latest_lightcone(
        self,
        *,
        include_details: bool = False,
        refresh: bool = False,
        **filters: Any,
    ) -> LightCone | None:
        items = await self.list_lightcones(sort_by="id", ascending=True, refresh=refresh, **filters)
        if not items:
            return None
        latest = max(items, key=lambda item: item.id)
        detail = await self.get_lightcone_detail(latest.id) if include_details else None
        return LightCone(summary=latest, detail=detail, locale=self.language)

    async def get_lightcone_detail(self, identifier: int | str, *, refresh: bool = False) -> LightConeDetail:
        payload = await self._detail("lightcone", identifier, refresh=refresh)
        assert payload is not None
        return LightConeDetail.model_validate({"id": int(identifier), **payload})
    async def list_relics(
        self,
        *,
        search: str | None = None,
        sort_by: str = "id",
        ascending: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> list[RelicSetSummary]:
        await self._prepare(refresh)
        payload = await self._catalog("relicset.json")
        items = [
            RelicSetSummary.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        items = filter_relics(items, search=search, language=self.language)
        items = apply_extra_filters(items, filters)
        if sort_by == "name":
            return sorted(
                items,
                key=lambda item: (item.display_name(self.language) or "").casefold(),
                reverse=not ascending,
            )
        return sorted(items, key=lambda item: item.id, reverse=not ascending)

    async def get_relic(
        self,
        identifier: int | str | None = None,
        *,
        name: str | None = None,
        search: str | None = None,
        include_details: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> RelicSet | None:
        needle = name or search
        if identifier is not None and not str(identifier).isdigit() and needle is None:
            needle = str(identifier)
        items = await self.list_relics(search=needle, refresh=refresh, **filters)
        if identifier is not None and str(identifier).isdigit():
            summary = next((item for item in items if str(item.id) == str(identifier)), None)
        else:
            summary = items[0] if items else None
        if summary is None:
            return None
        detail = await self.get_relic_detail(summary.id) if include_details else None
        return RelicSet(summary=summary, detail=detail, locale=self.language)

    async def get_latest_relic(
        self,
        *,
        include_details: bool = False,
        refresh: bool = False,
        **filters: Any,
    ) -> RelicSet | None:
        items = await self.list_relics(refresh=refresh, **filters)
        if not items:
            return None
        summary = max(items, key=lambda item: item.id)
        detail = await self.get_relic_detail(summary.id) if include_details else None
        return RelicSet(summary=summary, detail=detail, locale=self.language)

    async def get_relic_detail(self, identifier: int | str, *, refresh: bool = False) -> RelicSetDetail:
        payload = await self._detail("relicset", identifier, refresh=refresh)
        assert payload is not None
        return RelicSetDetail.model_validate({"id": int(identifier), **payload})

    async def list_monsters(
        self,
        *,
        rank: str | None = None,
        weakness: str | None = None,
        search: str | None = None,
        sort_by: str = "id",
        ascending: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> list[MonsterSummary]:
        await self._prepare(refresh)
        payload = await self._catalog("monster.json")
        items = [
            MonsterSummary.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        items = filter_monsters(
            items, rank=rank, weakness=weakness, search=search, language=self.language
        )
        items = apply_extra_filters(items, filters)
        if sort_by == "name":
            return sorted(
                items,
                key=lambda item: (item.display_name(self.language) or "").casefold(),
                reverse=not ascending,
            )
        return sorted(items, key=lambda item: item.id, reverse=not ascending)

    async def get_monster(
        self,
        identifier: int | str | None = None,
        *,
        name: str | None = None,
        rank: str | None = None,
        weakness: str | None = None,
        search: str | None = None,
        include_details: bool = True,
        refresh: bool = False,
        **filters: Any,
    ) -> Monster | None:
        needle = name or search
        if identifier is not None and not str(identifier).isdigit() and needle is None:
            needle = str(identifier)
        items = await self.list_monsters(
            rank=rank,
            weakness=weakness,
            search=needle,
            refresh=refresh,
            **filters,
        )
        if identifier is not None and str(identifier).isdigit():
            summary = next((item for item in items if str(item.id) == str(identifier)), None)
        else:
            summary = items[0] if items else None
        if summary is None:
            return None
        detail = await self.get_monster_detail(summary.id) if include_details else None
        return Monster(summary=summary, detail=detail, locale=self.language)

    async def get_latest_monster(
        self,
        *,
        include_details: bool = False,
        refresh: bool = False,
        **filters: Any,
    ) -> Monster | None:
        items = await self.list_monsters(refresh=refresh, **filters)
        if not items:
            return None
        summary = max(items, key=lambda item: item.id)
        detail = await self.get_monster_detail(summary.id) if include_details else None
        return Monster(summary=summary, detail=detail, locale=self.language)

    async def get_monster_detail(self, identifier: int | str, *, refresh: bool = False) -> MonsterDetail:
        payload = await self._detail("monster", identifier, refresh=refresh)
        assert payload is not None
        return MonsterDetail.model_validate({"id": int(identifier), **payload})

    async def get_monster_stats(
        self, identifier: int | str, *, refresh: bool = False
    ) -> MonsterStats | None:
        await self._prepare(refresh)
        payload = await self._cache.load_json("monstervalue.json", required=False) or {}
        entry = payload.get(str(identifier))
        if not entry:
            return None
        return MonsterStats.model_validate({"id": int(identifier), **entry})
    async def list_endgames(
        self,
        mode: str = "maze",
        *,
        live: bool | None = None,
        include_future: bool = True,
        refresh: bool = False,
    ) -> list[EndgameSeason]:
        canonical = mode_key(mode)
        schedules = await self.list_maze(
            mode=canonical,
            live=live,
            include_future=include_future,
            refresh=refresh,
        )
        return [
            EndgameSeason(
                mode=canonical,
                schedule=schedule,
                detail=await self._endgame_detail_for(canonical, schedule.id),
            )
            for schedule in schedules
        ]

    async def list_maze(
        self,
        *,
        mode: str = "maze",
        live: bool | None = None,
        include_future: bool = True,
        refresh: bool = False,
    ) -> list[MazeSchedule]:
        canonical = mode_key(mode)
        await self._prepare(refresh)
        if canonical == "maze_peak":
            payload = await self._catalog("maze_peak.json")
            items = [
                PeakSchedule.from_entry(identifier, value, mode=canonical)
                for identifier, value in payload.items()
                if isinstance(value, dict)
            ]
            return sorted(items, key=lambda item: item.id)
        payload = await self._catalog(f"{canonical}.json")
        version = await self._version_map(canonical)
        items = []
        for identifier, value in payload.items():
            if not isinstance(value, dict):
                continue
            item = MazeSchedule.from_entry(
                identifier,
                value,
                mode=canonical,
                version=version.get(str(identifier)),
            )
            items.append(item)
        if live is not None:
            items = [item for item in items if item.is_live == live]
        if not include_future:
            now = as_utc()
            items = [item for item in items if item.begins_at is None or item.begins_at <= now]
        return sorted(items, key=lambda item: (item.begins_at or datetime.min.replace(tzinfo=as_utc().tzinfo), item.id))

    async def get_maze(
        self,
        identifier: int | str,
        *,
        mode: str = "maze",
        refresh: bool = False,
    ) -> MazeSchedule | None:
        return next(
            (
                item
                for item in await self.list_maze(mode=mode, refresh=refresh, include_future=True)
                if str(item.id) == str(identifier)
            ),
            None,
        )

    def _current_from_items(
        self, items: list[MazeSchedule], canonical: str
    ) -> MazeSchedule | None:
        if not items:
            return None
        if canonical == "maze_peak":
            return items[-1]
        now = as_utc()
        # A live window is authoritative. Several upcoming/test seasons have
        # ``begin`` dates that are already in the past, so only seasons with a
        # real live window may be considered "live".
        live = [
            item
            for item in items
            if item.has_live_window
            and item.live_begins_at
            and item.live_ends_at
            and item.live_begins_at <= now <= item.live_ends_at
        ]
        if live:
            return max(live, key=lambda item: (item.live_begins_at, item.id))
        scheduled = [item for item in items if item.has_live_window and item.live_begins_at]
        upcoming = [item for item in scheduled if item.live_begins_at > now]
        if upcoming:
            return min(upcoming, key=lambda item: (item.live_begins_at, item.id))
        if scheduled:
            past = [item for item in scheduled if item.live_ends_at and item.live_ends_at <= now]
            if past:
                return max(past, key=lambda item: (item.live_ends_at, item.id))
            return max(scheduled, key=lambda item: (item.live_begins_at, item.id))
        # No live data at all (e.g. a brand-new test season): use sequence order.
        return max(items, key=lambda item: item.id)

    def _next_from_items(
        self,
        items: list[MazeSchedule],
        canonical: str,
        current: MazeSchedule | None,
    ) -> MazeSchedule | None:
        if not items:
            return None
        if canonical == "maze_peak":
            if current is None:
                return None
            later = [item for item in items if item.id > current.id]
            return min(later, key=lambda item: item.id) if later else None
        if current is None:
            upcoming = [
                item
                for item in items
                if item.has_live_window and item.live_begins_at and item.live_begins_at > as_utc()
            ]
            return min(upcoming, key=lambda item: (item.live_begins_at, item.id)) if upcoming else None
        # Seasons are published in sequence. Pick the next scheduled live
        # window when one exists; otherwise fall back to the next ID. Never
        # use test dates here: they can precede the live window by weeks.
        if current.has_live_window and current.live_ends_at:
            later = [
                item
                for item in items
                if item.id != current.id
                and item.has_live_window
                and item.live_begins_at
                and item.live_begins_at >= current.live_ends_at
            ]
            if later:
                return min(later, key=lambda item: (item.live_begins_at, item.id))
        later = [item for item in items if item.id > current.id]
        return min(later, key=lambda item: item.id) if later else None

    async def get_current_maze(
        self, *, mode: str = "maze", refresh: bool = False
    ) -> MazeSchedule | None:
        canonical = mode_key(mode)
        items = await self.list_maze(
            mode=canonical, refresh=refresh, include_future=True
        )
        return self._current_from_items(items, canonical)

    async def get_next_maze(
        self,
        *,
        mode: str = "maze",
        after: MazeSchedule | None = None,
        refresh: bool = False,
    ) -> MazeSchedule | None:
        canonical = mode_key(mode)
        items = await self.list_maze(mode=canonical, refresh=refresh, include_future=True)
        current = after or self._current_from_items(items, canonical)
        return self._next_from_items(items, canonical, current)

    async def get_current_endgame(
        self, mode: str = "maze", *, refresh: bool = False
    ) -> EndgameSeason | None:
        canonical = mode_key(mode)
        schedule = await self.get_current_maze(mode=canonical, refresh=refresh)
        if schedule is None:
            return None
        return EndgameSeason(
            canonical,
            schedule,
            await self._endgame_detail_for(canonical, schedule.id),
        )

    async def get_next_endgame(
        self, mode: str = "maze", *, refresh: bool = False
    ) -> EndgameSeason | None:
        canonical = mode_key(mode)
        schedule = await self.get_next_maze(mode=canonical, refresh=refresh)
        if schedule is None:
            return None
        return EndgameSeason(
            canonical,
            schedule,
            await self._endgame_detail_for(canonical, schedule.id),
        )

    async def list_peaks(self, *, refresh: bool = False) -> list[PeakSchedule]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("maze_peak.json", required=True) or {}
        return sorted(
            (
                PeakSchedule.from_entry(identifier, value, mode="maze_peak")
                for identifier, value in payload.items()
                if isinstance(value, dict)
            ),
            key=lambda item: item.id,
        )

    async def get_peak(
        self, identifier: int | str, *, refresh: bool = False
    ) -> PeakSchedule | None:
        return next(
            (item for item in await self.list_peaks(refresh=refresh) if str(item.id) == str(identifier)),
            None,
        )

    async def get_peak_detail(
        self, identifier: int | str, *, refresh: bool = False
    ) -> PeakDetail:
        payload = await self._detail("maze_peak", identifier, refresh=refresh)
        assert payload is not None
        return PeakDetail.model_validate({"id": int(identifier), "mode": "maze_peak", **payload})

    async def get_current_peak(self, *, refresh: bool = False) -> PeakSchedule | None:
        items = await self.list_peaks(refresh=refresh)
        return items[-1] if items else None

    async def get_next_peak(self, *, refresh: bool = False) -> PeakSchedule | None:
        items = await self.list_peaks(refresh=refresh)
        current = items[-1] if items else None
        if current is None:
            return None
        later = [item for item in items if item.id > current.id]
        return min(later, key=lambda item: item.id) if later else None
    async def get_endgame_detail(
        self, identifier: int | str, *, mode: str = "maze", refresh: bool = False
    ) -> EndgameDetail:
        canonical = mode_key(mode)
        if canonical == "maze_peak":
            return await self.get_peak_detail(identifier, refresh=refresh)
        payload = await self._detail(canonical, identifier, refresh=refresh)
        assert payload is not None
        if isinstance(payload, list):
            payload = {"level": payload}
        return EndgameDetail.model_validate(
            {"id": int(identifier), "mode": canonical, **payload}
        )

    async def get_latest_endgame_detail(
        self, mode: str = "maze", *, refresh: bool = False
    ) -> EndgameDetail | PeakDetail | None:
        season = await self.get_current_endgame(mode, refresh=refresh)
        return season.detail if season else None

    async def get_live_boss(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> BossEncounter | None:
        return await self._boss_for("current", mode, refresh=refresh)

    async def get_next_boss(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> BossEncounter | None:
        return await self._boss_for("next", mode, refresh=refresh)

    async def _boss_for(
        self, which: str, mode: str, *, refresh: bool = False
    ) -> BossEncounter | None:
        canonical = mode_key(mode)
        schedule = (
            await self.get_current_maze(mode=canonical, refresh=refresh)
            if which == "current"
            else await self.get_next_maze(mode=canonical, refresh=refresh)
        )
        if schedule is None:
            return None
        detail = await self._endgame_detail_for(canonical, schedule.id)
        if detail is None:
            return None
        stage = detail.boss_stage
        monster_ids: list[int] = []
        if isinstance(detail, PeakDetail):
            monster_ids = list(detail.boss_ids)
            if stage:
                monster_ids.extend(stage.monster_ids)
        else:
            monster_ids = list(detail.boss_ids)
            if stage:
                monster_ids = [*monster_ids, *stage.monster_ids]
        monster_ids = list(dict.fromkeys(monster_ids))
        bosses: list[Monster] = []
        seen: set[int] = set()
        for identifier in monster_ids:
            monster = await self.get_monster(identifier, include_details=True)
            if monster is None:
                # Endgame stages often reference a variant id (e.g.
                # 203401404) while the catalog only has the base monster
                # (2034014). Resolve through the base monster's ``child``.
                monster = await self._resolve_variant_monster(identifier, refresh=refresh)
            if monster is not None and monster.id not in seen:
                if monster.detail is not None and getattr(monster.detail, "id", None):
                    base_id = int(monster.detail.id)
                else:
                    base_id = int(monster.id)
                if base_id in seen:
                    continue
                seen.add(base_id)
                bosses.append(monster)
        waves = stage.events if stage else []
        return BossEncounter(
            mode=canonical,
            season=schedule,
            stage=stage,
            detail=detail,
            bosses=bosses,
            waves=waves,
            monster_ids=monster_ids,
            locale=self.language,
        )

    async def get_current_boss_stages(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> EndgameDetail | PeakDetail | None:
        season = await self.get_current_endgame(mode, refresh=refresh)
        return season.detail if season else None

    async def get_next_boss_stages(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> EndgameDetail | PeakDetail | None:
        season = await self.get_next_endgame(mode, refresh=refresh)
        return season.detail if season else None

    async def _resolve_variant_monster(
        self, identifier: int | str, *, refresh: bool = False
    ) -> Monster | None:
        """Resolve stage variant IDs to their catalog base monster."""
        target = str(identifier)
        for summary in await self.list_monsters(refresh=refresh):
            if target == str(summary.id) or target in {str(child) for child in summary.child}:
                detail = await self.get_monster_detail(summary.id)
                return Monster(summary=summary, detail=detail, locale=self.language)
        return None

    def schedule_windows(self, schedule: MazeSchedule) -> dict[str, datetime | None]:
        """Return both deployment/test and live windows for a season."""
        return {
            "test_begins_at": parse_datetime(schedule.begin),
            "test_ends_at": parse_datetime(schedule.end),
            "live_begins_at": parse_datetime(schedule.live_begin),
            "live_ends_at": parse_datetime(schedule.live_end),
        }

    async def list_schedules(
        self,
        mode: str = "maze",
        *,
        window: str = "live",
        refresh: bool = False,
    ) -> list[MazeSchedule]:
        """List schedules ordered by the selected window.

        ``window='live'`` uses ``live_begin``/``live_end`` and falls back to
        test dates only when a season has no live window yet. ``window='test'``
        always uses ``begin``/``end``.
        """
        canonical = mode_key(mode)
        items = await self.list_maze(mode=canonical, refresh=refresh, include_future=True)
        if window not in {"live", "test"}:
            raise ValueError("window must be 'live' or 'test'")
        if window == "test":
            return sorted(
                items,
                key=lambda item: (
                    parse_datetime(item.begin) or datetime.min.replace(tzinfo=as_utc().tzinfo),
                    item.id,
                ),
            )
        return sorted(
            items,
            key=lambda item: (
                parse_datetime(item.live_begin)
                or datetime.max.replace(tzinfo=as_utc().tzinfo),
                item.id,
            ),
        )

    async def _endgame_detail_for(
        self, mode: str, identifier: int
    ) -> EndgameDetail | PeakDetail | None:
        try:
            if mode == "maze_peak":
                return await self.get_peak_detail(identifier)
            return await self.get_endgame_detail(identifier, mode=mode)
        except NanokaNotFoundError:
            return None

    async def _version_map(self, mode: str) -> dict[str, str]:
        if mode in {"maze", "maze_peak"}:
            payload = await self._cache.load_json(f"{mode}/version.json", required=False)
            if isinstance(payload, dict):
                result: dict[str, str] = {}
                for version, ids in payload.items():
                    if isinstance(ids, list):
                        for identifier in ids:
                            result[str(identifier)] = str(version)
                return result
        return {}
    async def list_items(
        self,
        *,
        search: str | None = None,
        category: str | None = None,
        rarity: int | None = None,
        refresh: bool = False,
        **filters: Any,
    ) -> list[ItemSummary]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("item_all.json", required=False)
        if payload is None:
            payload = await self._cache.load_json("item.json", required=False) or {}
        items = [
            ItemSummary.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        items = filter_items(items, search=search, category=category, rarity=rarity)
        items = apply_extra_filters(items, filters)
        return sorted(items, key=lambda item: item.id)

    async def get_item(
        self,
        identifier: int | str | None = None,
        *,
        name: str | None = None,
        search: str | None = None,
        refresh: bool = False,
        **filters: Any,
    ) -> ItemSummary | None:
        needle = name or search
        if identifier is not None and not str(identifier).isdigit() and needle is None:
            needle = str(identifier)
        items = await self.list_items(search=needle, refresh=refresh, **filters)
        if identifier is not None and str(identifier).isdigit():
            return next((item for item in items if str(item.id) == str(identifier)), None)
        return items[0] if items else None

    async def list_achievements(
        self,
        *,
        search: str | None = None,
        refresh: bool = False,
        **filters: Any,
    ) -> list[AchievementSeries]:
        await self._prepare(refresh)
        payload = await self._cache.load_json(
            "achievement/achievement.json", required=False
        ) or {}
        items = [
            AchievementSeries.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        if search:
            needle = search.casefold()
            items = [
                item
                for item in items
                if needle in (item.name or "").casefold()
                or any(needle in (achievement.name or "").casefold() for achievement in item.achievements)
            ]
        items = apply_extra_filters(items, filters)
        return sorted(items, key=lambda item: (-(item.priority or 0), item.id))

    async def get_achievement(
        self, identifier: int | str, *, refresh: bool = False
    ) -> AchievementSeries | None:
        return next(
            (
                item
                for item in await self.list_achievements(refresh=refresh)
                if str(item.id) == str(identifier)
            ),
            None,
        )

    async def get_latest_item(
        self, *, refresh: bool = False, **filters: Any
    ) -> ItemSummary | None:
        items = await self.list_items(refresh=refresh, **filters)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_achievement(
        self, *, refresh: bool = False, **filters: Any
    ) -> AchievementSeries | None:
        items = await self.list_achievements(refresh=refresh, **filters)
        return max(items, key=lambda item: item.id) if items else None

    async def list_currency_items(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyItem]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("currency/item.json", required=False) or {}
        items = [
            CurrencyItem.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_roles(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyRole]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("currency/role.json", required=False) or {}
        items = [
            CurrencyRole.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_traits(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyTrait]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("currency/trait.json", required=False) or {}
        items = [
            CurrencyTrait.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_augments(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyAugment]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("currency/augment.json", required=False) or {}
        items = [
            CurrencyAugment.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_buffs(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyBuff]:
        await self._prepare(refresh)
        payload = await self._cache.load_json("currency/buff.json", required=False) or {}
        items = [
            CurrencyBuff.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def get_currency_trait(self, identifier: int | str, *, refresh: bool = False) -> CurrencyTrait | None:
        return await self._find(self.list_currency_traits(refresh=refresh), identifier)

    async def get_currency_role(self, identifier: int | str, *, refresh: bool = False) -> CurrencyRole | None:
        return await self._find(self.list_currency_roles(refresh=refresh), identifier)

    async def get_latest_currency_trait(self, *, refresh: bool = False) -> CurrencyTrait | None:
        items = await self.list_currency_traits(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_role(self, *, refresh: bool = False) -> CurrencyRole | None:
        items = await self.list_currency_roles(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_item(self, *, refresh: bool = False) -> CurrencyItem | None:
        items = await self.list_currency_items(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_augment(self, *, refresh: bool = False) -> CurrencyAugment | None:
        items = await self.list_currency_augments(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_buff(self, *, refresh: bool = False) -> CurrencyBuff | None:
        items = await self.list_currency_buffs(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def _find(self, items_awaitable, identifier: int | str):
        items = await items_awaitable
        return next((item for item in items if str(item.id) == str(identifier)), None)
    async def fetch_asset(self, relative: str, *, refresh: bool = False) -> Path | None:
        """Download one asset by its CDN-relative path.

        ``relative`` is the path below ``https://static.nanoka.cc/assets/hsr/``
        (for example ``skillicons/SkillIcon_1415_Ultra.webp``). This avoids a
        full asset-bundle initialization when a card only needs a few icons.
        """
        await self._prepare(refresh)
        normalized = relative.replace("\\", "/").lstrip("/")
        path = self._cache.asset_file(normalized)
        if path.is_file() and not refresh:
            return path
        try:
            return await self._cache.asset(normalized)
        except NanokaAssetError:
            return None

    async def asset_path(self, value: str, *, refresh: bool = False) -> Path | None:
        """Resolve an icon path, ``kind:id`` key, or bare ID to a local file."""
        await self._prepare(refresh)
        specs = collect_asset_specs(self._cache.data_dir)
        relative = resolve_asset_path(value, specs)
        if relative is None:
            return None
        path = self._cache.asset_file(relative)
        return path if path.is_file() else None

    async def download_asset(self, value: str, *, refresh: bool = False) -> Path | None:
        """Resolve and lazily download a single asset when missing."""
        await self._prepare(refresh)
        specs = collect_asset_specs(self._cache.data_dir)
        relative = resolve_asset_path(value, specs)
        if relative is None:
            return None
        path = self._cache.asset_file(relative)
        if path.is_file():
            return path
        try:
            return await self._cache.asset(relative)
        except NanokaAssetError:
            return None

    async def character_assets(
        self, identifier: int | str, *, include_skills: bool = True, refresh: bool = False
    ) -> dict[str, Path]:
        """Return the icon bundle a character card usually needs."""
        detail = await self.get_character_detail(identifier, refresh=refresh)
        result: dict[str, Path] = {}
        wanted: dict[str, str] = {
            "icon": f"character:{identifier}",
            "round_icon": f"character_round:{identifier}",
            "drawcard": f"character_drawcard:{identifier}",
            "element": f"element:{detail.element}",
            "path": f"path:{detail.path_codename}",
        }
        if include_skills:
            for skill in detail.skills.values():
                if skill.type_name in {"Basic ATK", "Skill", "Ultimate", "Technique", "Talent"}:
                    suffix = skill_icon_suffix(skill)
                    if suffix:
                        wanted[f"skill:{skill.type_name}"] = f"stem:SkillIcon_{identifier}_{suffix}"
        for rank in detail.eidolons:
            if rank.icon:
                wanted[f"eidolon:{rank.id}"] = f"stem:{Path(rank.icon).stem}"
        for trace in detail.traces:
            if trace.icon:
                wanted[f"trace:{trace.point}"] = f"stem:{Path(trace.icon).stem}"
        wanted["relic_head"] = "relicslot:head"
        wanted["relic_body"] = "relicslot:body"
        for key, value in wanted.items():
            path = await self.download_asset(value, refresh=False)
            if path is not None:
                result[key] = path
        return result

    async def character_materials(
        self, identifier: int | str, *, refresh: bool = False
    ) -> dict[str, Any]:
        """Group ascension, trace, skill, cone, and relic data for build cards."""
        detail = await self.get_character_detail(identifier, refresh=refresh)
        trace_costs = [
            cost
            for trace in detail.traces
            for level in trace.levels
            for cost in level.material_list
        ]
        return {
            "ascension": [cost for stat in detail.stats.values() for cost in stat.cost],
            "traces": trace_costs,
            "skills": detail.skills,
            "lightcones": detail.lightcones,
            "relics": detail.relics,
            "teams": detail.teams,
        }


class _ResultWrapper:
    summary: Any
    detail: Any

    def __init__(self, summary: Any, detail: Any | None = None, locale: Locale | str = DEFAULT_LOCALE):
        self.summary = summary
        self.detail = detail
        self.locale = Locale.normalize(locale)

    def __getattr__(self, name: str):
        if name in {"summary", "detail", "locale"}:
            raise AttributeError(name)
        try:
            return getattr(self.summary, name)
        except AttributeError:
            detail = object.__getattribute__(self, "detail")
            if detail is None:
                raise
            return getattr(detail, name)

    def display_name(self, locale: Locale | str | None = None, *, fallback: bool = True) -> str | None:
        return self.summary.display_name(locale or self.locale, fallback=fallback)

    def __repr__(self) -> str:
        identifier = getattr(self.summary, "id", "?")
        return f"{type(self).__name__}(id={identifier}, name={self.display_name()!r})"


class Character(_ResultWrapper):
    pass


class LightCone(_ResultWrapper):
    pass


class RelicSet(_ResultWrapper):
    pass


class Monster(_ResultWrapper):
    pass


def matches_text(item: Any, search: str | None, language: Locale) -> bool:
    if not search:
        return True
    needle = search.casefold()
    for lang in (language.value, "en", "zh", "ja", "ko"):
        value = getattr(item, lang, None)
        if value and needle in str(value).casefold():
            return True
    for key in ("name", "item_name", "title"):
        value = getattr(item, key, None)
        if value and needle in str(value).casefold():
            return True
    return False


def normalize_filter(value: str | None) -> str | None:
    return value.strip().casefold().replace("-", "").replace("_", "") if value else None


def apply_extra_filters(items: Iterable[T], filters: dict[str, Any]) -> list[T]:
    if not filters:
        return list(items)
    result = list(items)
    for key, expected in filters.items():
        if expected is None:
            continue
        result = [item for item in result if getattr(item, key, None) == expected]
    return result

def _filter_characters(
    items: Iterable[CharacterSummary],
    *,
    element: str | None,
    path: str | None,
    rarity: int | None,
    released: bool | None,
    include_beta: bool,
    search: str | None,
    extra: dict[str, Any],
) -> list[CharacterSummary]:
    result = list(items)
    if not include_beta:
        result = [item for item in result if item.release is not None]
    if released is not None:
        result = [item for item in result if (item.release is not None) == released]
    if element:
        needle = normalize_filter(element)
        result = [item for item in result if normalize_filter(item.damage_type) == needle]
    if path:
        needle = normalize_filter(path)
        result = [
            item
            for item in result
            if normalize_filter(item.base_type) == needle
            or normalize_filter(item.path) == needle
        ]
    if rarity is not None:
        result = [item for item in result if item.stars == rarity]
    if search:
        result = [item for item in result if matches_text(item, search, DEFAULT_LOCALE)]
    return apply_extra_filters(result, extra)


def sort_characters(
    items: Iterable[CharacterSummary],
    *,
    sort_by: str,
    ascending: bool,
    locale: Locale | str,
) -> list[CharacterSummary]:
    loc = Locale.normalize(locale)
    keys = {
        "release": lambda item: (item.release is not None, item.release or 0, item.id),
        "id": lambda item: item.id,
        "rarity": lambda item: (item.stars or 0, item.id),
        "name": lambda item: (item.display_name(loc) or "").casefold(),
    }
    return sorted(items, key=keys.get(sort_by, keys["release"]), reverse=not ascending)


def filter_lightcones(
    items: Iterable[LightConeSummary],
    *,
    path: str | None,
    rarity: int | None,
    search: str | None,
    language: Locale | str,
) -> list[LightConeSummary]:
    loc = Locale.normalize(language)
    result = list(items)
    if path:
        needle = normalize_filter(path)
        result = [
            item
            for item in result
            if normalize_filter(item.base_type) == needle or normalize_filter(item.path) == needle
        ]
    if rarity is not None:
        result = [item for item in result if item.stars == rarity]
    if search:
        result = [item for item in result if matches_text(item, search, loc)]
    return result


def sort_lightcones(
    items: Iterable[LightConeSummary],
    *,
    sort_by: str,
    ascending: bool,
    locale: Locale | str,
) -> list[LightConeSummary]:
    loc = Locale.normalize(locale)
    keys = {
        "id": lambda item: item.id,
        "rarity": lambda item: (item.stars or 0, item.id),
        "name": lambda item: (item.display_name(loc) or "").casefold(),
        "atk": lambda item: (item.atk or 0, item.id),
    }
    return sorted(items, key=keys.get(sort_by, keys["id"]), reverse=not ascending)


def filter_relics(
    items: Iterable[RelicSetSummary], *, search: str | None, language: Locale | str
) -> list[RelicSetSummary]:
    if not search:
        return list(items)
    loc = Locale.normalize(language)
    return [item for item in items if matches_text(item, search, loc)]


def filter_monsters(
    items: Iterable[MonsterSummary],
    *,
    rank: str | None,
    weakness: str | None,
    search: str | None,
    language: Locale | str,
) -> list[MonsterSummary]:
    result = list(items)
    if rank:
        needle = normalize_filter(rank)
        result = [item for item in result if normalize_filter(item.rank) == needle]
    if weakness:
        needle = normalize_filter(weakness)
        result = [
            item for item in result if any(normalize_filter(weak) == needle for weak in item.weak)
        ]
    if search:
        result = [item for item in result if matches_text(item, search, Locale.normalize(language))]
    return result


def filter_items(
    items: Iterable[ItemSummary],
    *,
    search: str | None,
    category: str | None,
    rarity: int | None = None,
) -> list[ItemSummary]:
    result = list(items)
    if category:
        needle = normalize_filter(category)
        result = [
            item
            for item in result
            if normalize_filter(item.item_main_type) == needle
            or normalize_filter(item.item_sub_type) == needle
        ]
    if rarity is not None:
        result = [item for item in result if item.stars == rarity]
    if search:
        needle = search.casefold()
        result = [
            item
            for item in result
            if needle in (item.item_name or "").casefold()
            or needle in (item.item_desc or "").casefold()
        ]
    return result


def filter_named(items: Iterable[Any], search: str | None) -> list[Any]:
    if not search:
        return list(items)
    needle = search.casefold()
    return [item for item in items if needle in (getattr(item, "name", "") or "").casefold()]


def skill_icon_suffix(skill: Any) -> str | None:
    mapping = {
        "Basic ATK": "Normal",
        "Skill": "BP",
        "Ultimate": "Ultra",
        "Technique": "Maze",
        "Talent": "Passive",
    }
    return mapping.get(skill.type_name)


def resolve_asset_path(value: str, specs: dict[str, str]) -> str | None:
    if not value:
        return None
    normalized = value.replace("\\", "/").strip()
    if normalized.startswith("asset:"):
        normalized = normalized[6:]
    filename = normalized.split("/")[-1]
    stem = Path(filename).stem
    candidates = [
        normalized,
        value,
        f"stem:{stem}",
        f"avatar:{stem}",
        f"character:{stem}",
        f"lightcone:{stem}",
        f"relic:{stem}",
        f"monster:{stem}",
        f"item:{stem}",
        f"element:{stem.lower()}",
        f"path:{stem.lower()}",
    ]
    if ":" in normalized:
        candidates.insert(0, normalized)
    for key in candidates:
        if key in specs:
            return specs[key]
    lower = normalized.lower()
    if lower.startswith("spriteoutput/monsterfigure/"):
        return f"monstermiddleicon/{stem}.webp"
    if lower.startswith("spriteoutput/item"):
        return f"itemfigures/{stem}.webp"
    if lower.endswith((".webp", ".png", ".jpg", ".jpeg")):
        return normalized
    if normalized.isdigit():
        return f"avatarshopicon/{normalized}.webp"
    return None


__all__ = [
    "NanokaClient",
    "ModeName",
    "Character",
    "LightCone",
    "RelicSet",
    "Monster",
    "BossEncounter",
    "EndgameSeason",
    "resolve_asset_path",
]

