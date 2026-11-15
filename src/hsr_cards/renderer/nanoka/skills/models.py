"""Resolved skills, eidolons, measured text, and rich-message result types."""
from __future__ import annotations

from PIL import Image
from dataclasses import dataclass
from dataclasses import field
from hsr_cards.nanoka.models import CharacterRank
from hsr_cards.nanoka.models import CharacterSkill
from pathlib import Path
from pydantic import BaseModel
from pydantic import Field
from typing import Any
from hsr_cards.renderer.nanoka.skills.styles import DASH


@dataclass
class GlossaryTerm:
    """One deduplicated glossary entry with a raw parameterized description and numeric params."""
    key: str
    name: str
    desc: str
    params: list[float | int] = field(default_factory=list)


@dataclass
class SkillRow:
    """One referenced skill parameter with its style, level-one display and default-cap value."""
    index: int
    style: str
    first_display: str
    default_display: str
    default_value: float | int


@dataclass
class SkillGroup:
    """A normalized character/memosprite skill, parameter table, glossary and optional previous/diff runs."""
    key: str
    skill: CharacterSkill
    type_label: str
    tag_label: str
    target_label: str
    target_entries: list[tuple[str, str]]
    scope: str
    icon_code: str | None
    name: str
    desc: str
    raw_desc: str
    cap: int
    rows: list[SkillRow] = field(default_factory=list)
    level_rows: list[tuple[int, list[float | int]]] = field(default_factory=list)
    styles: dict[int, str] = field(default_factory=dict)
    table_columns: list[int] = field(default_factory=list)
    extras: list[GlossaryTerm] = field(default_factory=list)
    energy: str = DASH
    toughness: str = DASH
    sp_change: str = DASH
    diff_runs: list[tuple[str, str, tuple[int, int, int, int]]] | None = None
    change: str | None = None
    before: "SkillGroup | None" = None


@dataclass
class RankRow:
    """One ordered eidolon with normalized labels, parameter displays, glossary and optional comparison runs."""
    key: str
    rank: CharacterRank
    name: str
    desc: str
    raw_desc: str
    params: list[tuple[int, str, str]] = field(default_factory=list)
    extras: list[GlossaryTerm] = field(default_factory=list)
    diff_runs: list[tuple[str, str, tuple[int, int, int, int]]] | None = None
    change: str | None = None
    before: "RankRow | None" = None


@dataclass
class SkillPanel:
    """One drawable skill or continuation with shared group data and optional premeasured lines."""
    group: SkillGroup
    desc: str
    part: int = 1
    parts: int = 1
    extras: bool = True
    stats: bool = True
    lines: list[list[Piece]] | None = None


@dataclass
class SkillData:
    """Resolved character identity, skills/eidolons, stats, cached art and older/newer comparison metadata."""
    character_id: int
    locale: str
    version: str
    name: str
    description: str
    element_label: str
    path_label: str
    stars: int
    splash: Image.Image | None
    element_icon: Image.Image | None
    path_icon: Image.Image | None
    skill_icon_dir: Path
    rank_icon_dir: Path | None
    skills: list[SkillGroup]
    eidolons: list[RankRow]
    memosprite_name: str = ""
    memosprite_code: str = ""
    stats: dict[str, float] = field(default_factory=dict)
    bonuses: list[tuple[str, float, str]] = field(default_factory=list)
    sp_need: float = 0
    stats_before: dict[str, float] | None = None
    bonuses_before: list[tuple[str, float, str]] | None = None
    sp_need_before: float | None = None
    version_before: str = ""
    version_after: str = ""
    detail: Any = None
    items: dict[str, Any] = field(default_factory=dict)

    @property
    def comparison(self) -> bool:
        """Return whether both comparison build labels are present."""
        return bool(self.version_before and self.version_after)


class SkillTable(BaseModel):
    """One rich-message table with its section/dropdown label."""

    label: str
    table_id: str
    rows: list[list[str]] = Field(default_factory=list)


class SkillSections(BaseModel):
    """Key/value groups used beside each table in rich messages."""

    skills: dict[str, dict[str, str]] = Field(default_factory=dict)
    eidolons: dict[str, dict[str, str]] = Field(default_factory=dict)
    materials: dict[str, str] = Field(default_factory=dict)


class SkillsCardResult:
    """Rendered skills card plus rich-message table payloads.

    ``tables`` remains the backwards-compatible 2D array list. ``table_models``
    adds labels and stable ids, while ``sections`` carries the same labels
    shown on the card for direct use in Telegram rich messages.
    """

    def __init__(
        self,
        image: Image.Image,
        tables: list[list[list[str]]],
        dropdowns: dict[str, int],
        *,
        table_models: list[SkillTable] | None = None,
        sections: SkillSections | None = None,
    ):
        """Wrap a PIL image and rich-message tables/dropdown indices without saving them.

        tables is the legacy list of 2D rows; dropdowns maps labels to table indices.
        Optional table_models/sections supply validated rich payloads. When absent,
        models are derived from valid indices and sections default to empty groups.
        This result owns no provider client or file handle.
        """
        self.image = image
        self.tables = tables
        self.dropdowns = dropdowns
        self.table_models = table_models or [
            SkillTable(label=label, table_id=label, rows=tables[index])
            for label, index in dropdowns.items()
            if index < len(tables)
        ]
        self.sections = sections or SkillSections()

    def save(self, *args, **kwargs):
        """Forward destination/format/encoder arguments to PIL.Image.save; file and encoding errors propagate."""
        return self.image.save(*args, **kwargs)

    def to_json_dict(self) -> dict[str, object]:
        """Return JSON-compatible tables, dropdowns, labeled table models and sections, excluding the PIL image."""
        return {
            "tables": self.tables,
            "dropdowns": self.dropdowns,
            "table_models": [item.model_dump() for item in self.table_models],
            "sections": self.sections.model_dump(),
        }


@dataclass
class Piece:
    """One laid-out text segment with RGBA color, font weight and optional removal strikethrough."""
    text: str
    color: tuple[int, int, int, int]
    weight: str
    strike: bool = False
