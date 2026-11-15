"""Endgame card services and stable result types."""
from .results import EndgameCardResult, EndgameFloorCard

__all__ = ["EndgameCardResult", "EndgameFloorCard", "get_current_endgame_card", "get_next_endgame_card"]


def __getattr__(name: str):
    """Load card orchestration only when an entry point is requested."""
    if name in {"get_current_endgame_card", "get_next_endgame_card"}:
        from . import api
        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
