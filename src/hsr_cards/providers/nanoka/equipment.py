"""Light-cone and relic-set queries used by NanokaClient."""
from __future__ import annotations

from typing import Any


from .models import LightConeDetail, LightConeSummary, RelicSetDetail, RelicSetSummary


from .results import LightCone, RelicSet
from .catalogs import apply_extra_filters, filter_lightcones, sort_lightcones, filter_relics


class EquipmentQueries:
    """Query light-cone and relic-set summaries and details."""

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
        """List light-cone summaries by path, numeric rarity, or localized search.

        Extra filters compare attributes exactly. sort_by accepts id, rarity, name, or
        atk (default id), with ascending=True. Return [] for no matches. Refresh
        revalidates version/locale data; validation and cache/transport failures propagate.
        """
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
        """Find a light cone by numeric ID, localized name, or catalog filters.

        A nonnumeric identifier becomes a search term. Return the first sorted match
        with details by default, or None if absent. include_details=False skips detail
        loading. Refresh revalidates catalogs; missing requested details raise
        NanokaNotFoundError and cache/transport/model failures propagate.
        """
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
        """Return the highest-ID matching light cone, or None for an empty catalog.

        Details are omitted by default. Filters follow list_lightcones; refresh
        revalidates cached data and detail/cache/transport errors propagate.
        """
        items = await self.list_lightcones(sort_by="id", ascending=True, refresh=refresh, **filters)
        if not items:
            return None
        latest = max(items, key=lambda item: item.id)
        detail = await self.get_lightcone_detail(latest.id) if include_details else None
        return LightCone(summary=latest, detail=detail, locale=self.language)

    async def get_lightcone_detail(self, identifier: int | str, *, refresh: bool = False) -> LightConeDetail:
        """Load a light-cone detail model by numeric ID for this version/locale.

        refresh=True revalidates data. Missing details raise NanokaNotFoundError;
        invalid IDs/models and cache/transport failures propagate.
        """
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
        """List relic-set summaries by localized search and exact attribute filters.

        sort_by=name orders by localized name; other values use ID, ascending by
        default. Return [] for no matches. Refresh revalidates version/locale data;
        validation and cache/transport failures propagate.
        """
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
        """Find a relic set by numeric ID, localized name, or summary filters.

        A nonnumeric identifier is a search term. Return the first match with details
        by default, or None if absent. include_details=False skips detail loading;
        refresh revalidates catalogs and detail/cache/transport errors propagate.
        """
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
        """Return the highest-ID matching relic set, or None if no set matches.

        Details are omitted by default; filters follow list_relics. Refresh revalidates
        cached data and missing-detail/cache/transport failures propagate.
        """
        items = await self.list_relics(refresh=refresh, **filters)
        if not items:
            return None
        summary = max(items, key=lambda item: item.id)
        detail = await self.get_relic_detail(summary.id) if include_details else None
        return RelicSet(summary=summary, detail=detail, locale=self.language)

    async def get_relic_detail(self, identifier: int | str, *, refresh: bool = False) -> RelicSetDetail:
        """Load a relic-set detail model by numeric ID for this version/locale.

        refresh=True revalidates data. Missing details raise NanokaNotFoundError;
        invalid IDs/models and cache/transport failures propagate.
        """
        payload = await self._detail("relicset", identifier, refresh=refresh)
        assert payload is not None
        return RelicSetDetail.model_validate({"id": int(identifier), **payload})
