"""Compatibility API for Prydwen tier-list data."""
from __future__ import annotations
import asyncio
from ..providers.prydwen.models import TIER_LIST_URL, GameMode, RoleHeader, TierCharacter, TierRole, Tier, TierGroup, TierListData
from ..providers.prydwen.parsing.tiers import parse_tier_list, _normalize_mode
from ..providers.prydwen.parsing.tier_dom import _parse_dom
from ..providers.prydwen.http import fetch_html as _fetch_html

async def fetch_tier_list(
    url: str = TIER_LIST_URL,
    *,
    game_mode: GameMode = "MOC",
    timeout: float = 30.0,
    proxy: str | None = None,
) -> TierListData:
    """Fetch MOC/PF/AS rankings as TierListData with source and update metadata.

    url defaults to the public tier page. game_mode aliases are case-insensitive;
    timeout is positive seconds and proxy applies to both HTTP and HTTPS.
    Runs HTTP in a worker and closes its scraper. Invalid input/missing rankings
    raise ValueError; request/dependency errors propagate. No files are written.
    """
    _normalize_mode(game_mode)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    html = await asyncio.to_thread(_fetch_html, url, timeout, proxy)
    return parse_tier_list(html, game_mode=game_mode, source=url)


__all__ = ["TIER_LIST_URL", "GameMode", "RoleHeader", "Tier", "TierCharacter", "TierGroup", "TierListData", "TierRole", "fetch_tier_list", "parse_tier_list"]
