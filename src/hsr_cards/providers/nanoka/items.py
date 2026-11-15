"""Item, achievement, and Currency Wars catalog queries."""
from __future__ import annotations

from typing import Any


from .models import (
    AchievementSeries,
    CurrencyAugment,
    CurrencyBuff,
    CurrencyItem,
    CurrencyRole,
    CurrencyTrait,
    ItemSummary,
)


from .catalogs import apply_extra_filters, filter_items, filter_named


class ItemsQueries:
    """Query item, achievement, and currency catalogs."""

    async def list_items(
        self,
        *,
        search: str | None = None,
        category: str | None = None,
        rarity: int | None = None,
        refresh: bool = False,
        **filters: Any,
    ) -> list[ItemSummary]:
        """List items by category, numeric rarity, name/description search, and attributes.

        Prefer item_all.json and fall back to item.json when unavailable. Return
        matching summaries in ID order, or [] if absent. Refresh revalidates the
        version/locale cache; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("item_all.json", required=False)
        if payload is None:
            payload = await self._read_json("item.json", required=False) or {}
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
        """Find an item by numeric ID, name/search text, or catalog filters.

        Nonnumeric identifiers become search terms. Return the first ID-ordered match
        or None; filters follow list_items. Refresh revalidates version/locale data
        and validation/cache/transport errors propagate.
        """
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
        """List achievement series by series/achievement name search and exact attributes.

        Return series ordered by descending priority then ID, or [] if unavailable.
        Refresh revalidates locale/version data; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json(
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
        """Return an achievement series by numeric ID, or None if absent.

        The identifier names a series, not an individual achievement. Refresh revalidates
        locale/version data and model/cache/transport errors propagate.
        """
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
        """Return the highest-ID item matching list_items filters, or None.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_items(refresh=refresh, **filters)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_achievement(
        self, *, refresh: bool = False, **filters: Any
    ) -> AchievementSeries | None:
        """Return the highest-ID achievement series matching the supplied filters, or None.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_achievements(refresh=refresh, **filters)
        return max(items, key=lambda item: item.id) if items else None

    async def list_currency_items(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyItem]:
        """List Currency Wars items, optionally filtered by case-insensitive name search.

        Return [] when the optional catalog is absent. Refresh revalidates the
        version/locale cache; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("currency/item.json", required=False) or {}
        items = [
            CurrencyItem.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_roles(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyRole]:
        """List Currency Wars roles, optionally filtered by case-insensitive name search.

        Return [] when the optional catalog is absent. Refresh revalidates the
        version/locale cache; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("currency/role.json", required=False) or {}
        items = [
            CurrencyRole.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_traits(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyTrait]:
        """List Currency Wars traits, optionally filtered by case-insensitive name search.

        Return [] when the optional catalog is absent. Refresh revalidates the
        version/locale cache; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("currency/trait.json", required=False) or {}
        items = [
            CurrencyTrait.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_augments(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyAugment]:
        """List Currency Wars augments, optionally filtered by case-insensitive name search.

        Return [] when the optional catalog is absent. Refresh revalidates the
        version/locale cache; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("currency/augment.json", required=False) or {}
        items = [
            CurrencyAugment.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def list_currency_buffs(self, *, search: str | None = None, refresh: bool = False) -> list[CurrencyBuff]:
        """List Currency Wars buffs, optionally filtered by case-insensitive name search.

        Return [] when the optional catalog is absent. Refresh revalidates the
        version/locale cache; model/cache/transport errors propagate.
        """
        await self._prepare(refresh)
        payload = await self._read_json("currency/buff.json", required=False) or {}
        items = [
            CurrencyBuff.from_entry(identifier, value)
            for identifier, value in payload.items()
            if str(identifier).isdigit() and isinstance(value, dict)
        ]
        return filter_named(items, search)

    async def get_currency_trait(self, identifier: int | str, *, refresh: bool = False) -> CurrencyTrait | None:
        """Return a Currency Wars trait by numeric ID, or None if absent.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        return await self._find(self.list_currency_traits(refresh=refresh), identifier)

    async def get_currency_role(self, identifier: int | str, *, refresh: bool = False) -> CurrencyRole | None:
        """Return a Currency Wars role by numeric ID, or None if absent.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        return await self._find(self.list_currency_roles(refresh=refresh), identifier)

    async def get_latest_currency_trait(self, *, refresh: bool = False) -> CurrencyTrait | None:
        """Return the highest-ID Currency Wars trait, or None for an empty catalog.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_currency_traits(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_role(self, *, refresh: bool = False) -> CurrencyRole | None:
        """Return the highest-ID Currency Wars role, or None for an empty catalog.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_currency_roles(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_item(self, *, refresh: bool = False) -> CurrencyItem | None:
        """Return the highest-ID Currency Wars item, or None for an empty catalog.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_currency_items(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_augment(self, *, refresh: bool = False) -> CurrencyAugment | None:
        """Return the highest-ID Currency Wars augment, or None for an empty catalog.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_currency_augments(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def get_latest_currency_buff(self, *, refresh: bool = False) -> CurrencyBuff | None:
        """Return the highest-ID Currency Wars buff, or None for an empty catalog.

        Refresh revalidates version/locale data; model/cache/transport errors propagate.
        """
        items = await self.list_currency_buffs(refresh=refresh)
        return max(items, key=lambda item: item.id) if items else None

    async def _find(self, items_awaitable, identifier: int | str):
        items = await items_awaitable
        return next((item for item in items if str(item.id) == str(identifier)), None)
