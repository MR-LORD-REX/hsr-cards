"""Resolved endgame data; these objects contain no live provider clients."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from PIL import Image
from ...core.text import format_hp
from ...core.types import GameMode
from ...nanoka.models import MazeSchedule, StageLevel
from .modes import EffectInfo


@dataclass
class HpBar:
    """One computed monster HP amount and optional one-based phase label."""
    amount: float
    phase: int | None = None


@dataclass
class CorrosionTarget:
    """An additional corrosion-affected target with base/bonus HP and resolved or pending artwork."""
    identifier: int
    name: str
    icon: Image.Image | None
    hp: float | None
    bonus_hp: float | None
    bonus_ratio: float | None
    icon_asset: str = ""


@dataclass
class MonsterInfo:
    """A wave enemy variant with spawn count, weaknesses, phase HP, corrosion and artwork."""
    identifier: int
    name: str
    icon: Image.Image | None
    hp: float | None
    weaknesses: list[str]
    hp_bars: list[HpBar] = field(default_factory=list)
    corrosion_ratio: float | None = None
    corrosion_hp: float | None = None
    count: int = 1
    icon_asset: str = ""

    @property
    def hp_text(self) -> str:
        """Format one/equal/mixed phase HP bars for display; missing HP is represented as HP ?."""
        if self.hp_bars:
            first = self.hp_bars[0].amount
            if len(self.hp_bars) == 1:
                return f"HP {format_hp(first)}"
            if len(self.hp_bars) > 1 and all(abs(bar.amount - first) < 1 for bar in self.hp_bars):
                return f"HP {format_hp(first)} x{len(self.hp_bars)}"
            return " / ".join(
                f"P{bar.phase or index} {format_hp(bar.amount)}"
                for index, bar in enumerate(self.hp_bars, start=1)
            )
        return f"HP {format_hp(self.hp)}" if self.hp is not None else "HP ?"


@dataclass
class NodeInfo:
    """One logical endgame node with full waves, recommended elements, corrosion and mode effects."""
    number: int
    level: int | None
    waves: list[list[MonsterInfo]]
    invasion_level: int | None = None
    elements: list[str] = field(default_factory=list)
    corrosion_ratio: float | None = None
    corrosion_desc: str | None = None
    corrosion_targets: list[CorrosionTarget] = field(default_factory=list)
    label: str | None = None
    season_effects: list[EffectInfo] = field(default_factory=list)
    stage_effects: list[EffectInfo] = field(default_factory=list)


@dataclass
class FloorCardData:
    """Resolved floor identity, dates, effects, conditions and nodes for drawing without a provider client."""
    mode: GameMode
    season: MazeSchedule
    floor: int
    stage: StageLevel
    stage_name: str
    season_name: str
    buff_name: str
    buff_text: str
    conditions: list[str]
    special: str | None
    nodes: list[NodeInfo]
    elements: list[str]
    status: str
    version: str
    begins_at: datetime | None
    ends_at: datetime | None
    element_icons: dict[str, Image.Image] = field(default_factory=dict)
    season_effects: list[EffectInfo] = field(default_factory=list)
    grit_effects: list[EffectInfo] = field(default_factory=list)
