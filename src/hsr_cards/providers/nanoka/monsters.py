"""Monster identity, detail, variant, and scaling queries."""
from __future__ import annotations

from typing import Any


from .models import MonsterDetail, MonsterStats, MonsterSummary


from .results import Monster
from .catalogs import apply_extra_filters, filter_monsters


class MonstersQueries:
    """Query monster catalogs, variants, and scaling records."""

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
        """List monster summaries filtered by rank, weakness, localized search, and attributes.

        Rank/weakness/search are case-insensitive. sort_by=name uses localized names;
        other values use ID, ascending by default. Return [] for no matches. Refresh
        revalidates version/locale data; validation and cache/transport errors propagate.
        """
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
        """Find a monster by numeric ID, localized name, or catalog filters.

        A nonnumeric identifier becomes search text. Return the first match with
        details by default, or None when absent. include_details=False skips details;
        refresh revalidates catalogs and detail/cache/transport failures propagate.
        """
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
        """Return the highest-ID matching monster, or None for an empty catalog.

        Details are omitted by default. Filters follow list_monsters; refresh
        revalidates cached data and detail/cache/transport errors propagate.
        """
        items = await self.list_monsters(refresh=refresh, **filters)
        if not items:
            return None
        summary = max(items, key=lambda item: item.id)
        detail = await self.get_monster_detail(summary.id) if include_details else None
        return Monster(summary=summary, detail=detail, locale=self.language)

    async def get_monster_detail(self, identifier: int | str, *, refresh: bool = False) -> MonsterDetail:
        """Load monster detail and variant models by numeric base ID.

        refresh=True revalidates version/locale data. Missing details raise
        NanokaNotFoundError; invalid IDs/models and cache/transport failures propagate.
        """
        payload = await self._detail("monster", identifier, refresh=refresh)
        assert payload is not None
        return MonsterDetail.model_validate({"id": int(identifier), **payload})

    async def get_monster_stats(
        self, identifier: int | str, *, refresh: bool = False
    ) -> MonsterStats | None:
        """Return base scaling stats from monstervalue.json by numeric ID, or None if absent.

        refresh=True revalidates data. This does not apply stage HP/difficulty modifiers;
        validation and cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("monstervalue.json", required=False) or {}
        entry = payload.get(str(identifier))
        if not entry:
            return None
        return MonsterStats.model_validate({"id": int(identifier), **entry})
