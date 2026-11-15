"""Endgame schedule and boss queries; live windows remain authoritative."""
from __future__ import annotations

from datetime import datetime


from .cache import mode_key
from .exceptions import NanokaNotFoundError
from .models import EndgameDetail, MazeSchedule, PeakDetail, PeakSchedule, as_utc, parse_datetime


from .results import BossEncounter, EndgameSeason, Monster


class SchedulesQueries:
    """Select endgame seasons using authoritative live windows."""

    async def list_endgames(
        self,
        mode: str = "maze",
        *,
        live: bool | None = None,
        include_future: bool = True,
        refresh: bool = False,
    ) -> list[EndgameSeason]:
        """Load schedules and optional details for a canonical mode or supported alias.

        Accept live filtering and include_future=True; missing details stay None.
        Return [] for no schedules. Refresh revalidates data; invalid modes raise
        ValueError and cache/transport/model failures propagate. Undated AA schedules
        retain their existing sequence semantics; this API does not render AA cards.
        """
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
        """List mode schedules in start-date/ID order, including future seasons by default.

        Modes accept canonical names and MOC/PF/AS/AA aliases. live=None disables
        filtering; include_future=False excludes dated future starts. AA remains
        ID-ordered because it has no dependable date windows. Refresh revalidates
        locale/version data; unknown modes and cache/transport/model failures propagate.
        """
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
        """Return a schedule by numeric ID in the requested canonical mode or alias, or None.

        Refresh revalidates version/locale data; invalid modes and cache/transport/model
        failures propagate. Details are not loaded.
        """
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
        """Select the current schedule using authoritative live windows, or None if empty.

        Fallbacks preserve the nearest scheduled window then sequence IDs when undated;
        AA keeps its highest-ID behavior. Mode aliases are accepted. Refresh revalidates
        data; invalid modes and cache/transport/model errors propagate.
        """
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
        """Select the next published schedule after after or the current schedule.

        Prefer subsequent live windows, then the next ID; test dates do not select
        the next season. Return None when no successor exists. Mode aliases are
        accepted; refresh revalidates data and cache/transport/model errors propagate.
        """
        canonical = mode_key(mode)
        items = await self.list_maze(mode=canonical, refresh=refresh, include_future=True)
        current = after or self._current_from_items(items, canonical)
        return self._next_from_items(items, canonical, current)

    async def get_current_endgame(
        self, mode: str = "maze", *, refresh: bool = False
    ) -> EndgameSeason | None:
        """Return the current mode schedule with optional detail data, or None.

        Selection follows get_current_maze. Missing detail remains None; refresh
        revalidates version/locale data and invalid-mode/cache/transport errors propagate.
        """
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
        """Return the next mode schedule with optional detail data, or None.

        Selection follows get_next_maze. Missing detail remains None; refresh
        revalidates version/locale data and invalid-mode/cache/transport errors propagate.
        """
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
        """List undated AA peak schedules in ascending ID order.

        Refresh revalidates version/locale data. Missing/invalid required catalog and
        transport failures propagate; this does not enable AA floor cards.
        """
        await self._prepare(refresh)
        payload = await self._read_json("maze_peak.json", required=True) or {}
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
        """Return an AA schedule by numeric ID, or None if no peak matches.

        Refresh revalidates data and catalog/model/transport failures propagate.
        """
        return next(
            (item for item in await self.list_peaks(refresh=refresh) if str(item.id) == str(identifier)),
            None,
        )

    async def get_peak_detail(
        self, identifier: int | str, *, refresh: bool = False
    ) -> PeakDetail:
        """Load AA peak detail data by numeric ID without enabling AA floor cards.

        Refresh revalidates version/locale data. Missing documents raise
        NanokaNotFoundError; invalid IDs/models and cache/transport failures propagate.
        """
        payload = await self._detail("maze_peak", identifier, refresh=refresh)
        assert payload is not None
        return PeakDetail.model_validate({"id": int(identifier), "mode": "maze_peak", **payload})

    async def get_current_peak(self, *, refresh: bool = False) -> PeakSchedule | None:
        """Return the highest-ID AA schedule, or None if the catalog is empty.

        This preserves the undated AA fallback; it does not establish a live date.
        Refresh revalidates data and catalog/model/transport failures propagate.
        """
        items = await self.list_peaks(refresh=refresh)
        return items[-1] if items else None

    async def get_next_peak(self, *, refresh: bool = False) -> PeakSchedule | None:
        """Return a published AA successor, currently None under the highest-ID fallback.

        No reliable AA date selection is added here. Refresh revalidates data and
        catalog/model/transport failures propagate.
        """
        items = await self.list_peaks(refresh=refresh)
        current = items[-1] if items else None
        if current is None:
            return None
        later = [item for item in items if item.id > current.id]
        return min(later, key=lambda item: item.id) if later else None

    async def get_endgame_detail(
        self, identifier: int | str, *, mode: str = "maze", refresh: bool = False
    ) -> EndgameDetail:
        """Load parsed detail data by numeric season ID and canonical mode or alias.

        AA routes to peak detail data. Missing documents raise NanokaNotFoundError;
        refresh revalidates version/locale data and invalid-mode/model/cache/transport
        failures propagate. This data operation does not enable AA rendering.
        """
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
        """Return detail data for the highest published season ID, or None if empty.

        Mode aliases are accepted; refresh revalidates data. Missing details and
        invalid-mode/model/cache/transport failures propagate.
        """
        season = await self.get_current_endgame(mode, refresh=refresh)
        return season.detail if season else None

    async def get_live_boss(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> BossEncounter | None:
        """Resolve current-season boss identities, variants, waves, and stage data.

        Default mode is PF (maze_extra); aliases are accepted. Return None without a
        schedule, otherwise BossEncounter even if detail/boss data is absent. Refresh
        revalidates version/locale data; cache/transport/model failures propagate.
        """
        return await self._boss_for("current", mode, refresh=refresh)

    async def get_next_boss(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> BossEncounter | None:
        """Resolve next-season boss identities, variants, waves, and stage data.

        Default mode is PF (maze_extra); aliases are accepted. Return None without a
        successor, otherwise BossEncounter. Refresh revalidates version/locale data;
        invalid-mode/cache/transport/model failures propagate.
        """
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
        """Return current-season detail/stages, or None if the season/detail is absent.

        Default mode is PF; aliases are accepted. Refresh revalidates version/locale
        data and invalid-mode/cache/transport/model failures propagate.
        """
        season = await self.get_current_endgame(mode, refresh=refresh)
        return season.detail if season else None

    async def get_next_boss_stages(
        self, mode: str = "maze_extra", *, refresh: bool = False
    ) -> EndgameDetail | PeakDetail | None:
        """Return next-season detail/stages, or None if the season/detail is absent.

        Default mode is PF; aliases are accepted. Refresh revalidates version/locale
        data and invalid-mode/cache/transport/model failures propagate.
        """
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
            payload = await self._read_json(f"{mode}/version.json", required=False)
            if isinstance(payload, dict):
                result: dict[str, str] = {}
                for version, ids in payload.items():
                    if isinstance(ids, list):
                        for identifier in ids:
                            result[str(identifier)] = str(version)
                return result
        return {}
