from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import HonkaiStarrail

from .prydwen.builds import PrydwenClient
from .nanoka import Locale, NanokaClient

__version__ = "1.0.2"
__author__ = "sora"

__all__ = [
    "HonkaiStarrail",
    "PrydwenClient",
    "NanokaClient",
    "Locale",
    "get_character_info",
    "get_LC_info",
    "LCInfoCardResult",
    "get_relic_info",
    "RelicInfoCardResult",
    "get_item_info",
    "ItemInfoCardResult",
    "get_character_skills",
    "EndgameCardResult",
    "EndgameFloorCard",
    "get_current_endgame_card",
    "get_next_endgame_card",
    "render_all_info",
    "render_all_skills",
    "RedeemCode",
    "Reward",
    "tier_list",
    "TierListData",
    "fetch_tier_list",
    "parse_tier_list",
]


def __getattr__(name: str):
    """Expose the player-card client and Nanoka APIs without eager imports.

    ``HonkaiStarrail`` validates HoYoLAB cookies at import time, so importing
    the package must not pull it in for callers that only want Nanoka cards.
    """
    if name == "PrydwenClient":
        from .prydwen.builds import PrydwenClient

        return PrydwenClient
    if name == "HonkaiStarrail":
        from .client import HonkaiStarrail

        return HonkaiStarrail
    if name in {"NanokaClient", "Locale"}:
        from .nanoka import Locale, NanokaClient

        return {"NanokaClient": NanokaClient, "Locale": Locale}[name]
    if name == "tier_list":
        from .renderer.prydwen import tier_list

        return tier_list
    if name in {"TierListData", "fetch_tier_list", "parse_tier_list"}:
        from .prydwen import tier_list as tier_list_module

        return getattr(tier_list_module, name)
    if name in {"RedeemCode", "Reward"}:
        from .prydwen.codes import RedeemCode, Reward

        return {"RedeemCode": RedeemCode, "Reward": Reward}[name]
    if name in {
        "get_character_info",
        "get_LC_info",
        "LCInfoCardResult",
        "get_relic_info",
        "RelicInfoCardResult",
        "get_item_info",
        "ItemInfoCardResult",
        "EndgameCardResult",
        "EndgameFloorCard",
        "get_current_endgame_card",
        "get_next_endgame_card",
        "get_character_skills",
        "render_all_info",
        "render_all_skills",
    }:
        from .renderer import nanoka

        return getattr(nanoka, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
