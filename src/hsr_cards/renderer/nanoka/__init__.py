"""Lazy compatibility exports for Nanoka card services and render primitives."""
from importlib import import_module

__all__ = [
    "BatchCardResult", "BatchRenderResult", "CharacterData", "InfoCardResult",
    "build_card_data", "build_comparison_card_data", "build_comparison_skills",
    "build_skill_data", "close_all", "get_character_info", "get_character_skills",
    "get_LC_info", "LCInfoCardResult", "get_relic_info", "RelicInfoCardResult",
    "get_item_info", "ItemInfoCardResult", "EndgameCardResult", "EndgameFloorCard",
    "get_current_endgame_card", "get_next_endgame_card", "load_character",
    "normalize_locale", "parse_versions", "render_all_info", "render_all_skills",
    "render_detail", "render_full",
]
_COMPAT_EXPORTS = set(__all__) | {
    "Image", "Path", "RenderedCardCache", "Sequence", "_batch_identifiers",
    "_run_batch", "dataclass", "default_rendered_cache_dir", "field", "skills_load_character",
}


def __getattr__(name: str):
    """Load the requested historical export; unknown names raise AttributeError."""
    if name not in _COMPAT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module("hsr_cards.services.endgame.api" if name in {
        "EndgameCardResult", "EndgameFloorCard", "get_current_endgame_card", "get_next_endgame_card"
    } else "hsr_cards.services.characters")
    return getattr(module, name)


def __dir__() -> list[str]:
    """List historical exports without loading their implementations."""
    return sorted(set(globals()) | set(__all__))
