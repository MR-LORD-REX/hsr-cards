from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import HonkaiStarrail

__version__ = "1.0.2"
__author__ = "sora"

__all__ = [
    "HonkaiStarrail",
    "NanokaClient",
    "Locale",
    "get_character_info",
    "get_character_skills",
    "render_all_info",
    "render_all_skills",
]


def __getattr__(name: str):
    """Expose the player-card client and Nanoka APIs without eager imports.

    ``HonkaiStarrail`` validates HoYoLAB cookies at import time, so importing
    the package must not pull it in for callers that only want Nanoka cards.
    """
    if name == "HonkaiStarrail":
        from .client import HonkaiStarrail

        return HonkaiStarrail
    if name in {"NanokaClient", "Locale"}:
        from .nanoka import Locale, NanokaClient

        return {"NanokaClient": NanokaClient, "Locale": Locale}[name]
    if name in {
        "get_character_info",
        "get_character_skills",
        "render_all_info",
        "render_all_skills",
    }:
        from .renderer import nanoka

        return getattr(nanoka, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
