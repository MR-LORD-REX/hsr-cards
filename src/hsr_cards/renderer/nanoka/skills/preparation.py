"""Adapt Nanoka skill parameters, caps, labels, and glossary data without IO."""
from __future__ import annotations

from hsr_cards.nanoka.models import CharacterRank
from hsr_cards.nanoka.models import CharacterSkill
from hsr_cards.nanoka.models import SkillExtra
import re
from hsr_cards.renderer.nanoka.skills.models import GlossaryTerm, RankRow, SkillGroup, SkillRow
from hsr_cards.renderer.nanoka.skills.styles import DASH, KIND_COLOR, PARAM_RE, TAG_LABELS, TAG_RE, TYPE_FALLBACKS, TYPE_ICONS, TYPE_ORDER


def normalize_breaks(text: str) -> str:
    """Nanoka JSON stores paragraph breaks as literal backslash-n text."""
    return text.replace(chr(92)*2 + "n", chr(92) + "n")


def plain(text: str | None) -> str:
    """Strip markup/style annotations and normalize paragraph escapes while retaining numbered parameter markers; None returns empty text."""
    if not text:
        return ""
    text = TAG_RE.sub("", normalize_breaks(text))
    text = PARAM_RE.sub(lambda match: f"#{match.group(1)}", text)
    # Block/box glyphs are intentionally redacted in the source; the text
    # faces on Windows have no glyph for them, so draw a visible placeholder.
    return re.sub(r"[ \t]+", " ", text).strip()


def format_number(value: float | int, style: str) -> str:
    """Format a Nanoka parameter using its template style.

    Nanoka templates encode percentages outside the parameter marker:
    ``#1[i]%``. The trailing ``%`` is part of ``style``, so it must survive
    parsing. Only percentage styles get a percent sign; integer and decimal
    styles are fixed values (``#2[i]`` turns, ``#3[f1]`` points) and are
    rendered bare.
    """
    percent = "%" in style
    base = style.replace("%", "")
    number = float(value) * (100 if percent else 1)
    if base == "i" and abs(number - round(number)) < 0.005:
        text = f"{round(number):d}"
    else:
        digits = 3 if abs(number * 1000 - round(number * 1000)) < 0.05 else 2
        text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    text = text or "0"
    return f"{text}%" if percent else text


def raw_number(value: float | int) -> str:
    """Return a Nanoka parameter at its native precision for table payloads."""
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.12g}"


def value_kind(style: str) -> str:
    """Classify a Nanoka style so percentages read differently from fixed values."""
    if "%" in style:
        return "percent"
    return "integer" if style.replace("%", "") == "i" else "decimal"


def value_color(style: str) -> tuple[int, int, int, int]:
    """Return the palette color for an integer, decimal or percentage Nanoka parameter style."""
    return KIND_COLOR[value_kind(style)]


def column_label(index: int) -> str:
    """Map a one-based parameter index to the table's A/B/C/D column label."""
    label = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def group_columns(group: SkillGroup) -> dict[int, str]:
    """Return one-based table-parameter indices mapped to alphabetical column markers."""
    return {index: column_label(index) for index in group.table_columns}


def level_pairs(skill: CharacterSkill) -> list[tuple[int, list[float | int]]]:
    """Return numerically ordered (skill level, parameter list) rows, omitting rows with no parameters."""
    return [
        (int(entry.level if entry.level is not None else key), entry.param_list)
        for key, entry in sorted(
            skill.level.items(),
            key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0,
        )
        if entry.param_list
    ]


def e0_cap(skill: CharacterSkill, scope: str) -> int:
    """Return the E0 display level cap for the skill type/scope, including technique and memosprite exceptions."""
    if scope == "memosprite":
        return 6
    kind = skill.type or ""
    if kind == "Normal":
        return 6
    if kind in {"BPSkill", "Ultra", "Talent", "Assist", "ElationDamage"}:
        return 10
    if kind == "Maze":
        return 1
    label = TYPE_FALLBACKS.get(kind, skill.type_name or "")
    if label in {"Memosprite Skill", "Memosprite Talent"}:
        return 6
    if label in {"Innate Trace", "Elation Skill"}:
        return 1
    return 10


def skill_rows(skill: CharacterSkill, scope: str) -> tuple[
    int,
    list[tuple[int, list[float | int]]],
    list[SkillRow],
    dict[int, str],
    list[int],
]:
    """Prepare a skill's default-cap parameter values and complete level table.

    Return (E0 cap, ordered level rows, referenced SkillRows, index-to-style mapping,
    all table-column indices). Default values use the highest available level at or
    below the cap; no level data yields empty collections. Numeric/model errors
    propagate. This adaptation performs no provider or filesystem IO.
    """
    levels = level_pairs(skill)
    cap = e0_cap(skill, scope)
    if not levels:
        return cap, [], [], {}, []
    styles = {
        int(match.group(1)): match.group(2) + (match.group(3) or "")
        for match in PARAM_RE.finditer(skill.desc or "")
    }
    indices = sorted({int(match.group(1)) for match in PARAM_RE.finditer(skill.desc or "")})
    columns = list(range(1, max(len(params) for _, params in levels) + 1))
    selected = levels[0][1]
    for level, params in levels:
        if level <= cap:
            selected = params
    first = levels[0][1]
    rows = []
    for index in indices:
        if index - 1 >= len(selected):
            continue
        style = styles.get(index, "f1")
        rows.append(
            SkillRow(
                index=index,
                style=style,
                first_display=format_number(first[index - 1], style) if index - 1 < len(first) else "",
                default_display=format_number(selected[index - 1], style),
                default_value=selected[index - 1],
            )
        )
    return cap, levels, rows, styles, columns


def iter_source_skills(source: dict) -> list[CharacterSkill]:
    """Validate source mappings as CharacterSkill objects in input order, inferring missing IDs from numeric keys."""
    skills = []
    for key, raw in source.items():
        if isinstance(raw, CharacterSkill):
            skills.append(raw)
            continue
        payload = dict(raw)
        if "id" not in payload:
            payload["id"] = int(key) if str(key).isdigit() else 0
        skills.append(CharacterSkill.model_validate(payload))
    return skills


def group_source(detail, scope: str) -> dict:
    """Return the character or memosprite skill mapping for scope, defaulting to an empty mapping."""
    if scope == "memosprite":
        return (detail.memosprite or {}).get("skills") or {}
    return detail.skills or {}


def glossary_terms(raw) -> list[GlossaryTerm]:
    """Normalize/deduplicate glossary mappings or SkillExtra objects by name/description; empty input returns []."""
    if not raw:
        return []
    items = raw.values() if isinstance(raw, dict) else raw
    result: list[GlossaryTerm] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if isinstance(item, SkillExtra):
            name_raw, desc_raw = item.name, item.desc
            params = list(item.param or item.param_list)
        elif isinstance(item, dict):
            name_raw, desc_raw = item.get("name"), item.get("desc")
            params = list(item.get("param") or item.get("param_list") or [])
        else:
            continue
        name = plain(name_raw)
        desc = desc_raw or ""
        if not name or not desc.strip():
            continue
        key = (name, desc)
        if key in seen:
            continue
        seen.add(key)
        result.append(GlossaryTerm(key=str(len(result)), name=name, desc=desc, params=params))
    return result


def sp_change_text(skill: CharacterSkill) -> str:
    """Format generated SP with +, consumed SP with -, or a dash when neither is specified."""
    if skill.bp_add is not None:
        return f"+{skill.bp_add}"
    need = skill.bp_need or 0
    if need > 0:
        return f"-{need}"
    return DASH


def target_text(skill: CharacterSkill) -> str:
    """Return uppercase target labels, preserving slash-separated target groups; absent tags return empty text."""
    tag = skill.tag or ""
    if not tag:
        return ""
    if "/" in tag:
        labels = [TAG_LABELS.get(part.strip(), part.strip()) for part in tag.split("/") if part.strip()]
        return " / ".join(labels).upper()
    label = TAG_LABELS.get(tag, "")
    if not label and tag.startswith("Single"):
        label = "Single Target"
    return label.upper()


def stance_values(skill: CharacterSkill) -> list[float]:
    """Nanoka stores toughness in third-points; the UI shows whole points."""
    return [round(float(value) / 3, 2) for value in (skill.show_stance_list or []) if value]


def stance_parts(skill: CharacterSkill) -> list[tuple[str, float]]:
    """Pair whole-point toughness values with target labels, using single/adjacent/AoE fallbacks when tags do not align."""
    values = stance_values(skill)
    if not values:
        return []
    tags = [part.strip() for part in (skill.tag or "").split("/") if part.strip()]
    labels = [TAG_LABELS.get(tag, tag) for tag in tags]
    if len(labels) == len(values) and all(labels):
        return list(zip(labels, values))
    if len(values) == 1:
        return [(TAG_LABELS.get(tags[0], target_text(skill).title()) if tags else "Toughness", values[0])]
    first = "Blast" if "Blast" in tags else "Single Target"
    labels = [first, "AoE"] if len(values) > 1 else [first]
    labels.extend("AoE" for _ in values[2:])
    return list(zip(labels[:len(values)], values))


def format_stance(value: float) -> str:
    """Format toughness with at most two decimals and no trailing zeros."""
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


def stance_text(skill: CharacterSkill) -> str:
    """Return labeled slash-separated whole-point toughness displays, or a dash for missing values."""
    parts = stance_parts(skill)
    if not parts:
        return DASH
    return " / ".join(
        f"{name}: {format_stance(value)}" if name else format_stance(value)
        for name, value in parts
    )


def skill_groups(detail) -> list[SkillGroup]:
    """Normalize and order drawable character/memosprite skills from a detail model.

    Skip empty descriptions and MazeNormal duplicates; merge matching type/name
    entries and attach E0 caps, all level values, target/SP/toughness labels and
    glossary terms. Return SkillGroup objects without downloading assets.
    Invalid provider models or numeric fields raise validation/conversion errors.
    """
    merged: dict[tuple[str, str], tuple[CharacterSkill, str]] = {}
    for scope in ("character", "memosprite"):
        for skill in iter_source_skills(group_source(detail, scope)):
            if skill.type == "MazeNormal":
                continue
            description = plain(skill.desc)
            if not description:
                continue
            label = TYPE_FALLBACKS.get(skill.type or "", skill.type_name or "Unknown")
            key = (label, plain(skill.name))
            existing = merged.get(key)
            if existing is None or len(description) > len(plain(existing[0].desc)):
                merged[key] = (skill, scope)
    groups = []
    for (label, _), (skill, scope) in merged.items():
        cap, levels, rows, styles, columns = skill_rows(skill, scope)
        entries = stance_parts(skill)
        target_entries = [] if entries else []
        groups.append(
            SkillGroup(
                key=str(skill.id),
                skill=skill,
                type_label=label.upper(),
                tag_label=TAG_LABELS.get(skill.tag or "", ""),
                target_label=target_text(skill),
                target_entries=target_entries,
                scope=scope,
                icon_code=TYPE_ICONS.get(label),
                name=plain(skill.name) or str(skill.id),
                desc=plain(skill.desc),
                raw_desc=skill.desc or "",
                cap=cap,
                rows=rows,
                level_rows=levels,
                styles=styles,
                table_columns=columns,
                extras=glossary_terms(skill.extra),
                energy=str(skill.sp_base) if skill.sp_base is not None else DASH,
                toughness=stance_text(skill),
                sp_change=sp_change_text(skill),
            )
        )
    return sorted(
        groups,
        key=lambda group: (
            TYPE_ORDER.get(TYPE_FALLBACKS.get(group.skill.type or "", group.skill.type_name or ""), 99),
            0 if group.scope == "character" else 1,
            group.name,
        ),
    )


def rank_rows(rank_map: dict) -> list[RankRow]:
    """Validate and numerically order eidolons, attaching display parameters and deduplicated glossary terms; no IO occurs."""
    result = []
    for key, raw in sorted(
        rank_map.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 0
    ):
        if isinstance(raw, CharacterRank):
            rank = raw
        else:
            payload = dict(raw)
            if "id" not in payload:
                payload["id"] = int(key) if str(key).isdigit() else 0
            rank = CharacterRank.model_validate(payload)
        styles = {
            int(match.group(1)): match.group(2) + (match.group(3) or "")
            for match in PARAM_RE.finditer(rank.desc or "")
        }
        params = []
        for index, value in enumerate(rank.param_list, start=1):
            style = styles.get(index, "i")
            params.append((index, format_number(value, style), style))
        result.append(
            RankRow(
                key=key,
                rank=rank,
                name=plain(rank.name) or key,
                desc=plain(rank.desc),
                raw_desc=rank.desc or "",
                params=params,
                extras=glossary_terms(rank.extra),
            )
        )
    return result
