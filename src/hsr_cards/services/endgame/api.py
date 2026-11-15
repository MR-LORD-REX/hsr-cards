"""Public endgame card orchestration with explicit provider ownership."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Sequence
from PIL import Image
from ...core.types import GameMode
from ...core.text import clean_text, expand_params, format_hp, format_number
from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import MazeSchedule
from ...renderer.nanoka.data import RenderedCardCache, normalize_locale
from ...renderer.nanoka.endgame.layout import render_floor_card
from ...renderer.nanoka.endgame.nodes import monster_row_height, node_panel_height, draw_node_panel
from ...renderer.nanoka.endgame.styles import *
from ...renderer.nanoka.endgame.drawing import rounded, draw_chip, draw_element_chip, draw_star, wrapped_lines
from ...renderer.common.images import paste_icon
from ...renderer.common.text import wrap_text
from .assets import load_assets, load_icon, monster_asset
from .data import *
from .hp import *
from .models import *
from .modes import EffectInfo, node_effects, node_wave_specs
from .results import EndgameCardResult, EndgameFloorCard
from .schedules import *


def _cache_name(mode: GameMode, season_id: int, floor: int, status: str) -> str:
    # Schedule badges must change when an upcoming season goes live.
    return f"ENDGAME_v2_{mode}_{season_id}_F{floor}_{status}"


async def _season_card(
    game_mode: GameMode,
    season: MazeSchedule,
    floors: Sequence[int] | int | None,
    *,
    locale: str,
    cache_dir: str | Path | None,
    proxy: str | None,
    rendered_cache_dir: str | Path | None,
    use_rendered_cache: bool,
    force_refresh: bool,
    client: NanokaClient | None = None,
) -> EndgameCardResult:
    if game_mode == "AA":
        raise NotImplementedError("Anomaly Arbitration cards are deferred until live schedules are available.")
    canonical = canonical_mode(game_mode)
    owns_client = client is None
    client = client if client is not None else NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        if owns_client:
            await client.initialize()
        payload = await client.get_endgame_payload(season.id, mode=canonical) if season.id is not None else None
        records = parse_stage_records(payload)
        if not records:
            raise ValueError(f"No stage data found for {game_mode} season {season.id}")
        grouped = group_floor_records(records)
        requested = normalize_floors(game_mode, floors) or sorted(grouped)
        missing = [floor for floor in requested if floor not in grouped]
        if missing:
            raise ValueError(f"{game_mode} season {season.id} has no floor(s): {', '.join(map(str, missing))}")
        status = season_status(season)
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        cards: list[EndgameFloorCard] = []
        for floor in requested:
            floor_records = grouped[floor]
            cached = None if force_refresh else cache.load(_cache_name(game_mode, season.id, floor, status), "endgame", client.version, locale=locale)
            cache_path = cache.path(_cache_name(game_mode, season.id, floor, status), "endgame", client.version, locale=locale)
            if cached is not None:
                stage_id = stage_identifier(floor_records[0])
                cards.append(EndgameFloorCard(cached, floor=floor, stage_id=stage_id, name=extract_stage_name(floor_records[0], floor), cache_path=cache_path))
                continue
            floor_data = await build_floor_data(client, season, floor, floor_records, mode=game_mode, status=status,
                season_payload=payload if isinstance(payload, dict) else None)
            await load_assets(client, floor_data)
            image = await asyncio.to_thread(render_floor_card, floor_data)
            if use_rendered_cache:
                cache_path = cache.save(image, _cache_name(game_mode, season.id, floor, status), "endgame", client.version, locale=locale)
            cards.append(EndgameFloorCard(image, floor=floor, stage_id=stage_identifier(floor_records[0]), name=floor_data.stage_name, cache_path=cache_path))
        return EndgameCardResult(
            game_mode=game_mode, season_id=season.id, season_name=(payload.get("name") if isinstance(payload, dict) else None) or extract_stage_name(records[0], 1),
            version=client.version, cards=cards, begins_at=season.live_begins_at, ends_at=season.live_ends_at,
            is_live=season.is_live,
        )
    finally:
        if owns_client:
            await client.close()


async def get_current_endgame_card(
    game_mode: GameMode = "MOC",
    floors: Sequence[int] | int | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
    client: NanokaClient | None = None,
) -> EndgameCardResult:
    """Render live MOC/PF/AS floor cards, one image per requested floor.

    game_mode accepts the suggested mode codes case-insensitively with whitespace
    trimmed. AA raises NotImplementedError until live schedules are reliable. floors
    is one integer or a sequence; None selects MOC 11/12 or PF/AS 3/4. Requested
    floors are deduplicated and sorted.

    Return EndgameCardResult with ordered floor cards, resolved provider version and
    authoritative live-window metadata. Missing live/stage data or absent floors
    raises ValueError; unsupported modes/locales and provider/render/file failures
    propagate. No player credentials or records are requested.

    locale defaults to en; cache_dir/proxy configure an internally created Nanoka
    client. An initialized client may be injected and stays caller-owned: its
    language overrides locale, including the rendered-cache suffix, and its cache/
    proxy settings remain active. Otherwise one operation-owned client is initialized,
    reused for all floors and closed even on failure.

    rendered_cache_dir defaults to .hsr_cards_rendered under the caller cwd.
    force_refresh bypasses generated-image reads; use_rendered_cache=False disables
    generated-image IO. Catalog/assets may still be requested and cached.
    """
    locale = normalize_locale(getattr(client, "language", None) or locale)
    game_mode = str(game_mode).strip().upper()  # type: ignore[assignment]
    canonical_mode(game_mode)
    if game_mode == "AA":
        raise NotImplementedError("Anomaly Arbitration cards are deferred until live schedules are available.")
    owns_client = client is None
    client = client if client is not None else NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        if owns_client:
            await client.initialize()
        season = await client.get_current_endgame(canonical_mode(game_mode))
        if season is None or not season.schedule.has_live_window or not season.schedule.is_live:
            raise ValueError(f"No live {game_mode} season is available")
        result = await _season_card(
            game_mode, season.schedule, floors, locale=locale, cache_dir=cache_dir, proxy=proxy,
            rendered_cache_dir=rendered_cache_dir, use_rendered_cache=use_rendered_cache,
            force_refresh=force_refresh, client=client,
        )
        return result
    finally:
        if owns_client:
            await client.close()


async def get_next_endgame_card(
    game_mode: GameMode = "MOC",
    floors: Sequence[int] | int | None = None,
    *,
    look_ahead: int | Literal["max"] = 1,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
    client: NanokaClient | None = None,
) -> EndgameCardResult | list[EndgameCardResult]:
    """Render upcoming MOC/PF/AS floor cards after the latest started live cycle.

    game_mode accepts trimmed, case-insensitive mode codes; AA raises
    NotImplementedError. floors accepts one integer or a sequence; None selects
    MOC 11/12 or PF/AS 3/4, sorted and deduplicated. look_ahead defaults to one;
    positive larger values or "max" request multiple successfully resolved seasons.

    Return one EndgameCardResult for look_ahead=1, otherwise a list ordered by live
    start time. Undated published seasons follow dated ones with UNSCHEDULED status
    and absent live dates. Missing/unrenderable seasons are skipped; an empty single
    request raises ValueError, while list requests may return []. Invalid mode,
    locale/look-ahead or provider/render/file failures propagate.

    locale defaults to en and cache_dir/proxy configure operation-created clients.
    An initialized injected client keeps its settings and ownership; its language
    overrides locale, including generated-image cache suffixes. Otherwise one client
    is initialized, reused across all seasons and closed even on failure.
    rendered_cache_dir defaults to the caller-relative .hsr_cards_rendered directory.
    force_refresh bypasses generated-image reads; use_rendered_cache=False disables
    generated-image IO. Provider catalogs/assets may still be requested and cached.
    """
    locale = normalize_locale(getattr(client, "language", None) or locale)
    game_mode = str(game_mode).strip().upper()  # type: ignore[assignment]
    canonical_mode(game_mode)
    if game_mode == "AA":
        raise NotImplementedError("Anomaly Arbitration cards are deferred until live schedules are available.")
    if look_ahead != "max" and int(look_ahead) < 1:
        raise ValueError("look_ahead must be at least 1 or 'max'")
    owns_client = client is None
    client = client if client is not None else NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        if owns_client:
            await client.initialize()
        canonical = canonical_mode(game_mode)
        items = await client.list_maze(mode=canonical, include_future=True)
        now = datetime.now(timezone.utc)
        started_ids = [item.id for item in items if item.has_live_window and item.live_begins_at <= now]
        anchor = max(started_ids) if started_ids else None
        later = [
            item for item in items
            if (anchor is None or item.id > anchor)
            and (not item.has_live_window or item.live_begins_at > now)
        ]
        later.sort(key=lambda item: (
            item.live_begins_at or datetime.max.replace(tzinfo=timezone.utc), item.id,
        ))
        results: list[EndgameCardResult] = []
        for season in later:
            try:
                result = await _season_card(
                    game_mode, season, floors, locale=locale, cache_dir=cache_dir, proxy=proxy,
                    rendered_cache_dir=rendered_cache_dir, use_rendered_cache=use_rendered_cache,
                    force_refresh=force_refresh, client=client,
                )
            except (ValueError, NanokaNotFoundError):
                continue
            results.append(result)
            if look_ahead != "max" and len(results) >= int(look_ahead):
                break
        if look_ahead == 1:
            if not results:
                raise ValueError(f"No upcoming {game_mode} season with stage data is available")
            return results[0]
        return results
    finally:
        if owns_client:
            await client.close()

__all__ = ["GameMode", "EndgameCardResult", "EndgameFloorCard", "get_current_endgame_card", "get_next_endgame_card"]
