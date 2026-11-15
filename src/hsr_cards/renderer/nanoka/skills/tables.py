"""Build skill tables and rich-message sections from resolved character data."""
from __future__ import annotations

from hsr_cards.renderer.nanoka.character_info import aggregate
from hsr_cards.renderer.nanoka.character_info import material_name
from hsr_cards.renderer.nanoka.character_info import skill_materials
from hsr_cards.renderer.nanoka.skills.header import ui
from hsr_cards.renderer.nanoka.skills.models import SkillData, SkillGroup, SkillSections
from hsr_cards.renderer.nanoka.skills.preparation import column_label, format_number, raw_number
from hsr_cards.renderer.nanoka.skills.styles import DASH


def group_table(group: SkillGroup) -> list[list[str]] | None:
    """Build header/level rows for a skill parameter table, using previous-to-current values for changes; missing tables return None."""
    if not group.level_rows or not group.table_columns:
        return None
    comparison = group.before is not None and group.change is not None
    table = [["#"] + [column_label(index) for index in group.table_columns]]
    previous = {
        level: params for level, params in (group.before.level_rows if group.before else [])
    }
    for level, params in group.level_rows:
        row = [f"Lv.{level}"]
        old_params = previous.get(level, [])
        for index in group.table_columns:
            style = group.styles.get(index, "f1")
            if index - 1 >= len(params):
                row.append("")
                continue
            value = format_number(params[index - 1], style) if comparison else raw_number(params[index - 1])
            if not comparison:
                row.append(value)
                continue
            old_value = (
                format_number(old_params[index - 1], style)
                if index - 1 < len(old_params)
                else DASH
            )
            row.append(value if old_value == value else f"{old_value} \u2192 {value}")
        table.append(row)
    return table


def build_tables(data: SkillData) -> tuple[list[list[list[str]]], dict[str, int]]:
    """Return legacy 2D table arrays plus unique label-to-table indices in skill order."""
    tables: list[list[list[str]]] = []
    dropdowns: dict[str, int] = {}
    for group in data.skills:
        table = group_table(group)
        if not table:
            continue
        label = f"{group.type_label} \u00b7 {group.name}"
        if label in dropdowns:
            label = f"{label} \u00b7 {group.key}"
        dropdowns[label] = len(tables)
        tables.append(table)
    return tables, dropdowns


def material_sections(data: SkillData) -> dict[str, str]:
    """Rich-message totals for the two material panels on the info card."""
    detail = data.detail
    items = data.items
    ascension = aggregate(cost for stat in detail.stats.values() for cost in stat.cost)
    skills = skill_materials(detail)
    result = {}
    for label, costs in (("ascension", ascension), ("skills", skills)):
        result[f"{label}_credits"] = f"{next((cost.amount for cost in costs if cost.item_id == 2), 0):,}"
        for cost in costs:
            if cost.item_id == 2:
                continue
            name = material_name(items, cost.item_id, data.locale)
            result[f"{label}:{name}"] = f"x{cost.amount:,}"
    return result


def build_sections(data: SkillData) -> SkillSections:
    """Return SkillSections with display-aligned skill/eidolon fields, change markers and material totals."""
    skills: dict[str, dict[str, str]] = {}
    for group in data.skills:
        label = f"{group.type_label} \u00b7 {group.name}"
        values = {
            "type": group.type_label,
            "target": group.target_label,
            "level": str(group.cap) if group.level_rows else ui(data, "passive"),
            "energy": group.energy,
            "toughness": group.toughness,
            "sp_change": group.sp_change,
            "description": group.desc,
        }
        if group.change:
            values["change"] = group.change
        skills[label] = values
    eidolons: dict[str, dict[str, str]] = {}
    for rank in data.eidolons:
        label = f"E{rank.key} \u00b7 {rank.name}"
        values = {"name": rank.name, "description": rank.desc}
        if rank.change:
            values["change"] = rank.change
        eidolons[label] = values
    return SkillSections(skills=skills, eidolons=eidolons, materials=material_sections(data))
