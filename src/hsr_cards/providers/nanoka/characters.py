"""Character catalog and detail queries used by NanokaClient."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from ...builds import find_builds, load_build_image
from .models import CharacterDetail, CharacterSummary


from .results import Character
from .catalogs import _filter_characters, sort_characters


class CharactersQueries:
    """Resolve character catalogs, details, and build assets."""

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
        """List character summaries matching catalog filters in the chosen order.

        Beta entries are included by default; released compares release timestamps.
        Path/element/search are case-insensitive, rarity is numeric, and extra filters
        compare summary attributes exactly. sort_by accepts release, id, rarity, or name
        (default release), with ascending=True. Refresh revalidates disk/network data.
        Return [] when no entries match; validation and cache/transport errors propagate.
        """
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
        """Find by numeric ID, localized name, or any list_characters catalog filter.

        A nonnumeric identifier becomes search text. Return the first sorted
        matching Character wrapper, or None if absent. Details are included by
        default; include_details=False skips their loading. Refresh revalidates
        version/locale data. Missing requested details raise NanokaNotFoundError;
        invalid ID/model and cache/transport failures propagate.
        """
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
        """Load a character detail model by numeric ID for this client locale/version.

        refresh=True revalidates cached data. Missing details raise NanokaNotFoundError;
        invalid IDs/models and cache/transport failures propagate.
        """
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
        Path/element/rarity filters follow list_characters. Details are omitted
        by default; return None for an empty catalog. Refresh revalidates
        version/locale data and detail/cache/transport failures propagate.
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
