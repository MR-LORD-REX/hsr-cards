"""Asset bundle resolution for Nanoka domain objects."""
from __future__ import annotations

from pathlib import Path
from typing import Any


from .cache import collect_asset_specs


from .catalogs import skill_icon_suffix, resolve_asset_path


class AssetsQueries:
    """Resolve cached icons and character material bundles."""

    async def fetch_asset(self, relative: str, *, refresh: bool = False) -> Path | None:
        """Download one asset by its CDN-relative path.

        ``relative`` is the path below ``https://static.nanoka.cc/assets/hsr/``
        (for example ``skillicons/SkillIcon_1415_Ultra.webp``). This avoids a
        full asset-bundle initialization when a card only needs a few icons.
        Missing assets return None. Refresh revalidates the configured cache;
        initialization/cache/transport failures propagate. Return the local Path
        from the provider API and retain its resolved version.
        """
        path = await self.api_client.fetch_asset(relative, refresh=refresh)
        self._sync_configuration()
        return path

    async def asset_path(self, value: str, *, refresh: bool = False) -> Path | None:
        """Resolve an icon path, ``kind:id`` key, or bare ID to a cached local file.

        Return None for unknown aliases or missing assets. This initializes the
        JSON cache and reads its catalogs but does not request the individual
        asset. Refresh revalidates data; cache/transport failures propagate.
        """
        await self._prepare(refresh)
        specs = collect_asset_specs(self._cache.data_dir)
        relative = resolve_asset_path(value, specs)
        if relative is None:
            return None
        path = self._cache.asset_file(relative)
        return path if path.is_file() else None

    async def download_asset(self, value: str, *, refresh: bool = False) -> Path | None:
        """Resolve an icon path, ``kind:id`` alias, or bare ID and fetch a missing asset.

        Return the local Path, or None when resolution/download is unavailable.
        Refresh revalidates the version/locale cache; catalog/cache/transport
        failures propagate and successful downloads update the asset manifest.
        """
        await self._prepare(refresh)
        specs = collect_asset_specs(self._cache.data_dir)
        relative = resolve_asset_path(value, specs)
        if relative is None:
            return None
        path = self._cache.asset_file(relative)
        if path.is_file():
            return path
        return await self.fetch_asset(relative)

    async def character_assets(
        self, identifier: int | str, *, include_skills: bool = True, refresh: bool = False
    ) -> dict[str, Path]:
        """Return available character art, element/path, eidolon/trace, and relic icons.

        identifier is numeric; include_skills=True also adds standard skill icons.
        Return an alias-to-local-Path mapping; unavailable assets are omitted.
        Refresh revalidates detail data and missing assets are downloaded. Missing
        detail raises NanokaNotFoundError; cache/transport/model errors propagate.
        """
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
        """Group character material requirements and recommended build data by numeric ID.

        Return ascension/trace costs, skills, lightcones, relics, and teams from
        the parsed detail model. Refresh revalidates version/locale data. Missing
        details raise NanokaNotFoundError; model/cache/transport errors propagate.
        """
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
