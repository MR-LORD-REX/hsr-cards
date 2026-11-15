"""Prydwen build-data extraction and static build-card rendering."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...clients.prydwen import PrydwenClient
from .models import (
    AssetRef,
    BuildCardData,
    CharacterIdentity,
    CharacterStats,
    EditorTeam,
    EditorTeamMember,
    LightConeRecommendation,
    RelicRecommendation,
    RelicWeightGroup,
    StatChoice,
    StatTarget,
    Synergy,
    TeamMode,
    TeamVariant,
    TracePriority,
)
from .teams import TeamIndex, build_team_index

__all__ = [
    "PrydwenClient",
    "AssetRef",
    "BuildCardData",
    "CharacterIdentity",
    "CharacterStats",
    "EditorTeam",
    "EditorTeamMember",
    "LightConeRecommendation",
    "RelicRecommendation",
    "RelicWeightGroup",
    "StatChoice",
    "StatTarget",
    "Synergy",
    "TeamIndex",
    "TeamMode",
    "TeamVariant",
    "TracePriority",
    "build_team_index",
]

def __getattr__(name: str):
    """Load the pipeline client only when requested, without opening transports."""
    if name == "PrydwenClient":
        from ...clients.prydwen import PrydwenClient
        return PrydwenClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
