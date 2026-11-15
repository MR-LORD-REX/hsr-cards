"""Translate Nanoka schedules and payloads into resolved floor data."""
from __future__ import annotations
import math
import re
from typing import Any, Sequence
from ...core.text import clean_text, expand_params
from ...core.types import GameMode
from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import MazeSchedule, MonsterDetail, StageEvent, StageLevel
from .assets import load_icon, monster_asset
from .hp import invasion_ratio, monster_hp_values
from .models import CorrosionTarget, FloorCardData, MonsterInfo
from .modes import EffectInfo, node_effects, node_wave_specs
from .models import NodeInfo
from .schedules import canonical_mode


def parse_stage_records(payload: Any) -> list[dict[str, Any]]:
    """Extract mapping stage records from a list, a level-list payload or one mapping; unsupported payloads return []."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        levels = payload.get("level")
        if isinstance(levels, list):
            return [item for item in levels if isinstance(item, dict)]
        return [payload]
    return []


def group_floor_records(records: Sequence[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """Group primary stages and pre_id/pre_level_id continuations by logical floor.

    Primary order supplies fallback floor numbers; a trailing Roman numeral overrides
    that index. Continuations stay with their primary so third nodes are preserved.
    Return floor-to-record-list mappings; invalid numeric identifiers raise ValueError.
    """
    primary: list[dict[str, Any]] = []
    continuations: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        pre_id = record.get("pre_id") or record.get("pre_level_id")
        if pre_id:
            continuations.setdefault(int(pre_id), []).append(record)
        else:
            primary.append(record)
    floors: dict[int, list[dict[str, Any]]] = {}
    for index, record in enumerate(primary, start=1):
        identifier = int(record.get("id") or index)
        floor = continue_floor_index(index, record)
        floors[floor] = [record, *continuations.get(identifier, [])]
    return floors


def continue_floor_index(index: int, record: dict[str, Any]) -> int:
    """Return a trailing parenthesized Roman-numeral floor number, or the supplied one-based fallback index."""
    name = clean_text(record.get("name"))
    match = re.search(r"\(([IVXLCDM]+)\)\s*$", name)
    if match:
        value = roman_to_int(match.group(1))
        if value:
            return value
    return index


def roman_to_int(value: str) -> int | None:
    """Convert Roman numeral symbols using subtractive arithmetic; empty/unknown symbols return None."""
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for char in reversed(value.upper()):
        digit = values.get(char)
        if digit is None:
            return None
        total = total - digit if digit < previous else total + digit
        previous = max(previous, digit)
    return total or None


def stage_identifier(record: dict[str, Any]) -> int | None:
    """Return an integer stage ID, or None when absent; invalid numeric values raise ValueError."""
    value = record.get("id")
    return int(value) if value is not None else None


def stage_from_record(record: dict[str, Any], mode: str = "maze") -> StageLevel:
    """Validate one raw record as StageLevel with a fallback Nanoka mode; schema errors propagate."""
    return StageLevel.model_validate({"mode": mode, **record})


def merge_stage(primary: StageLevel, extras: Sequence[StageLevel]) -> StageLevel:
    """Merge continuation-specific third-node fields into a validated primary stage.

    Return the primary unchanged when extras is empty; otherwise return a new
    StageLevel, preserving node-one/two fields and replacing nonempty continuation
    fields in order. Validation errors propagate; input objects are not mutated.
    """
    if not extras:
        return primary
    payload = primary.model_dump()
    for continuation in extras:
        # A continuation supplies the third node and its own wave/boss metadata.
        for key in ("challenge", "challenge_special", "event_id_list", "damage_type",
                    "infinite_list", "npc_monster_id_list", "boss_monster_id",
                    "boss_monster_config", "countdown"):
            value = getattr(continuation, key)
            if value:
                payload[key] = value
    return StageLevel.model_validate(payload)


def stage_events_by_node(stage: StageLevel) -> dict[int, list[StageEvent]]:
    """Return present node-one/two/three StageEvent lists keyed by their logical node number."""
    nodes: dict[int, list[StageEvent]] = {}
    if stage.event_id_list:
        nodes[3] = list(stage.event_id_list)
    if stage.event_id_list1:
        nodes[1] = list(stage.event_id_list1)
    if stage.event_id_list2:
        nodes[2] = list(stage.event_id_list2)
    return nodes


async def resolve_monster_record(client: NanokaClient, identifier: int) -> MonsterDetail | None:
    """Load a monster detail by ID, falling back through catalog child/variant IDs.

    Return MonsterDetail or None when no catalog entry resolves. Missing direct
    records trigger fallback; other provider/model failures propagate. Requests may
    write the borrowed client's provider cache without closing it.
    """
    try:
        return await client.get_monster_detail(identifier)
    except NanokaNotFoundError:
        pass
    target = str(identifier)
    for summary in await client.list_monsters():
        if target == str(summary.id) or target in {str(child) for child in summary.child}:
            return await client.get_monster_detail(summary.id)
    return None


async def hp_resolver(client: NanokaClient) -> tuple[Any, Any, Any]:
    """Load optional hard-level, elite-group and base-monster HP catalogs.

    Return (hard rows, elite rows, base-value mapping), replacing absent catalogs with
    empty containers. Cache/model failures propagate; the borrowed client retains
    its lifecycle and version/locale settings.
    """
    hard = await client.cache.load_json("HardLevelGroup.json", required=False) or []
    elite = await client.cache.load_json("EliteGroup.json", required=False) or []
    values = await client.cache.load_json("monstervalue.json", required=False) or {}
    return hard, elite, values


async def load_monster_info(
    client: NanokaClient,
    event: StageEvent,
    identifier: int,
    hard_rows: Sequence[dict[str, Any]],
    elite_rows: Sequence[dict[str, Any]],
    values: dict[str, Any],
    *,
    corrosion_ratio: float | None = None,
) -> MonsterInfo:
    """Resolve one wave enemy's display name, weaknesses, phase HP and optional corrosion.

    identifier selects the stage variant; hard_rows/elite_rows/values supply scaling
    catalogs. corrosion_ratio optionally adds HP based on the first bar. Return
    MonsterInfo with cached icon or None and an asset path for later loading; unknown
    details fall back to the numeric ID. Provider/model/conversion failures propagate.
    The supplied client is borrowed and may cache requested monster data.
    """
    detail = await resolve_monster_record(client, identifier)
    name = clean_text(detail.name) if detail and detail.name else str(identifier)
    variant = next((item for item in detail.child if item.id == identifier), None) if detail else None
    weaknesses = [weakness.lower() for weakness in (variant.stance_weak_list if variant else detail.weaknesses if detail else [])]
    bars = monster_hp_values(event, identifier, detail, hard_rows, elite_rows, values)
    hp = bars[0].amount if bars else None
    icon = load_icon(client, monster_asset(identifier, detail))
    corrosion_hp = None
    if corrosion_ratio and bars:
        corrosion_hp = bars[0].amount * corrosion_ratio
    return MonsterInfo(
        identifier=identifier, name=name, icon=icon, hp=hp, weaknesses=weaknesses,
        hp_bars=bars, corrosion_ratio=corrosion_ratio, corrosion_hp=corrosion_hp,
        icon_asset=monster_asset(identifier, detail),
    )


async def build_floor_data(
    client: NanokaClient,
    season: MazeSchedule,
    floor: int,
    records: Sequence[dict[str, Any]],
    *,
    mode: GameMode,
    status: str,
    season_payload: dict[str, Any] | None = None,
) -> FloorCardData:
    """Resolve a logical floor's nodes, waves, counts, HP, corrosion and effects.

    records must contain its primary stage followed by any continuations. mode selects
    MOC/PF/AS adapters; season_payload supplies full season buffs/options. status is
    the already resolved display label. Return FloorCardData with no provider client
    reference, ready for targeted artwork loading and synchronous drawing.

    Catalog/monster requests use the supplied client's version/locale cache and may
    write it. Missing optional data uses display fallbacks; schema/provider/conversion
    errors propagate. The supplied client stays borrowed and is not closed.
    """
    primary_record = records[0]
    season_payload = season_payload or {}
    stage_records = [stage_from_record(record, canonical_mode(mode)) for record in records]
    stage = merge_stage(stage_records[0], stage_records[1:])
    hard_rows, elite_rows, values = await hp_resolver(client)
    nodes: list[NodeInfo] = []
    for number, events in sorted(stage_events_by_node(stage).items()):
        event = events[0]
        ratio = invasion_ratio(event)
        affected = set(event.invasion.all_monster_ids) if event.invasion is not None else set()
        waves: list[list[MonsterInfo]] = []
        for wave_event, counts, hp_scale in node_wave_specs(stage, number, event, mode):
            wave = []
            for identifier, count in counts.items():
                info = await load_monster_info(
                    client, wave_event, identifier, hard_rows, elite_rows, values,
                    corrosion_ratio=ratio if identifier in affected else None,
                )
                info.count = count
                for bar in info.hp_bars:
                    bar.amount *= hp_scale
                if info.hp is not None:
                    info.hp *= hp_scale
                if info.corrosion_hp is not None and info.hp is not None:
                    info.corrosion_hp = math.floor(info.hp + 0.5) * info.corrosion_ratio
                wave.append(info)
            if wave:
                waves.append(wave)
        listed_ids = {monster.identifier for wave in waves for monster in wave}
        targets: list[CorrosionTarget] = []
        if event.invasion is not None:
            for slot in event.invasion.monster_list:
                identifier = getattr(slot, "monster_id", None) or getattr(slot, "resolved_id", None)
                if identifier is None:
                    identifier = next(iter(getattr(slot, "monster_ids", [])), None)
                if identifier is None or (mode in {"PF", "AS"} and identifier in listed_ids):
                    continue
                info = await load_monster_info(
                    client, event, identifier, hard_rows, elite_rows, values,
                    corrosion_ratio=ratio,
                )
                if info.corrosion_hp is None:
                    continue
                targets.append(CorrosionTarget(
                    identifier=identifier,
                    name=info.name,
                    icon=info.icon,
                    hp=info.hp,
                    bonus_hp=info.corrosion_hp,
                    bonus_ratio=ratio, icon_asset=info.icon_asset,
                ))
        season_effects, stage_effects = node_effects(stage, number, season_payload, expand_params)
        nodes.append(NodeInfo(
            number=number,
            level=event.level,
            waves=waves,
            invasion_level=event.invasion.level if event.invasion else None,
            corrosion_ratio=ratio,
            corrosion_desc=clean_text(event.invasion.desc) if event.invasion else None,
            corrosion_targets=targets,
            label="STARWARD MODE" if mode == "AS" and number == 3 else None,
            season_effects=season_effects, stage_effects=stage_effects,
        ))
    conditions: list[str] = []
    for challenge in stage.challenge:
        text = expand_params(challenge.name, challenge.params)
        if text:
            conditions.append(text)
    special = None
    if stage.challenge_special:
        item = stage.challenge_special[0]
        special = expand_params(item.name, item.params)
    season_name = season_payload.get("name") or extract_stage_name(primary_record, floor)
    buff = season_payload.get("buff") or primary_record
    buff_name = clean_text(buff.get("name")) or f"{season_name}  /  Stage {floor}"
    buff_text = expand_params(buff.get("desc"), buff.get("param") or buff.get("param_list") or [])
    elements: list[str] = []
    node_elements = {1: stage.damage_type1, 2: stage.damage_type2, 3: stage.damage_type}
    for node in nodes:
        node.elements = [value.lower() for value in node_elements.get(node.number, []) if value]
        for value in node.elements:
            if value not in elements:
                elements.append(value)
    return FloorCardData(
        mode=mode, season=season, floor=floor, stage=stage,
        stage_name=extract_stage_name(primary_record, floor),
        season_name=season_name,
        buff_name=buff_name,
        buff_text=buff_text, conditions=conditions, special=special, nodes=nodes,
        elements=elements, status=status, version=client.version,
        begins_at=season.live_begins_at, ends_at=season.live_ends_at,
        season_effects=[EffectInfo.from_payload(item, expand_params) for item in season_payload.get("option", [])],
        grit_effects=[EffectInfo.from_payload(item, expand_params) for item in season_payload.get("sub_option", [])],
    )


def extract_stage_name(record: dict[str, Any], floor: int) -> str:
    """Return a cleaned stage name without a trailing floor numeral, or Floor N when unnamed."""
    name = clean_text(record.get("name"))
    if not name:
        return f"Floor {floor}"
    return re.sub(r"\s*\([IVXLCDM]+\)\s*$", "", name).strip()
