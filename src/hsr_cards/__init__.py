"""Stable public exports, loaded without provider IO or session creation."""
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clients.main import HonkaiStarrail
    from .clients.nanoka import NanokaClient
    from .clients.prydwen import PrydwenClient
    from .core.types import GameMode
    from .providers.nanoka.locales import Locale
    from .services.characters import (
        BatchCardResult, BatchRenderResult, InfoCardResult,
        get_character_info, get_character_skills, render_all_info, render_all_skills,
    )
    from .services.endgame.api import get_current_endgame_card, get_next_endgame_card
    from .services.endgame.results import EndgameCardResult, EndgameFloorCard

__version__ = "1.0.2"
__author__ = "sora"

_EXPORTS = {
    "HonkaiStarrail": ".clients.main",
    "NanokaClient": ".clients.nanoka",
    "PrydwenClient": ".clients.prydwen",
    "Locale": ".providers.nanoka.locales",
    "GameMode": ".core.types",
    "get_character_info": ".services.characters",
    "get_character_skills": ".services.characters",
    "InfoCardResult": ".services.characters",
    "SkillsCardResult": ".renderer.nanoka.skills.models",
    "BatchCardResult": ".services.characters",
    "BatchRenderResult": ".services.characters",
    "render_all_info": ".services.characters",
    "render_all_skills": ".services.characters",
    "get_LC_info": ".renderer.nanoka.light_cone",
    "LCInfoCardResult": ".renderer.nanoka.light_cone",
    "get_relic_info": ".renderer.nanoka.relic",
    "RelicInfoCardResult": ".renderer.nanoka.relic",
    "get_item_info": ".renderer.nanoka.item",
    "ItemInfoCardResult": ".renderer.nanoka.item",
    "EndgameCardResult": ".services.endgame.results",
    "EndgameFloorCard": ".services.endgame.results",
    "get_current_endgame_card": ".services.endgame.api",
    "get_next_endgame_card": ".services.endgame.api",
    "RedeemCode": ".prydwen.codes",
    "Reward": ".prydwen.codes",
    "tier_list": ".renderer.prydwen.tier_list",
    "TierListData": ".prydwen.tier_list",
    "fetch_tier_list": ".prydwen.tier_list",
    "parse_tier_list": ".prydwen.tier_list",
}
__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve a public export on demand; unknown names raise AttributeError.

    Importing the package alone performs no filesystem discovery, cookie
    validation, HTTP requests, or session creation. Resolved exports are cached.
    """
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy exports in interactive discovery and editor suggestions."""
    return sorted(set(globals()) | set(__all__))
