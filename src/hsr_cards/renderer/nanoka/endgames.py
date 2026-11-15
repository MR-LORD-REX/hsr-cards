"""Telegram-friendly MOC, Pure Fiction, and Apocalyptic Shadow floor cards.

Anomaly Arbitration cards remain deferred until live schedules are available.
"""

from __future__ import annotations

import asyncio
import functools
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import MazeSchedule, MonsterDetail, StageEvent, StageLevel
from ...utils.hsrfonts import HSRFonts
from .data import RenderedCardCache, normalize_locale
from .endgame_modes import EffectInfo, node_effects, node_wave_specs

GameMode = Literal["MOC", "PF", "AS", "AA"]

W = 1080
M = 40
GAP = 20
BG = (10, 10, 20, 255)
BG2 = (15, 14, 28, 255)
PANEL = (26, 23, 42, 255)
PANEL2 = (32, 28, 51, 255)
EDGE = (66, 56, 92, 255)
TEXT = (246, 243, 252, 255)
BODY = (225, 220, 238, 255)
MUTED = (184, 177, 202, 255)
GOLD = (255, 205, 121, 255)
PURPLE = (198, 169, 255, 255)
CYAN = (146, 226, 238, 255)
RED = (255, 146, 154, 255)
LIVE = (146, 235, 178, 255)
UPCOMING = (255, 205, 121, 255)
ENDED = (184, 177, 202, 255)

MODE_NAMES = {"MOC": "MEMORY OF CHAOS", "PF": "PURE FICTION", "AS": "APOCALYPTIC SHADOW", "AA": "ANOMALY ARBITRATION"}
MODE_CANONICAL = {"MOC": "maze", "PF": "maze_extra", "AS": "maze_boss", "AA": "maze_peak"}
DEFAULT_FLOORS = {"MOC": (11, 12), "PF": (3, 4), "AS": (3, 4)}
ELEMENT_COLORS = {
    "physical": (238, 238, 238, 255), "fire": (255, 142, 102, 255),
    "ice": (133, 211, 255, 255), "thunder": (206, 145, 255, 255),
    "wind": (123, 232, 170, 255), "quantum": (138, 130, 255, 255),
    "imaginary": (255, 223, 115, 255),
}
ELEMENT_LABELS = {name: name.title() for name in ELEMENT_COLORS}
ICON_GLYPHS = {"physical": "z", "fire": "v", "ice": "w", "thunder": "y", "wind": "t", "quantum": "u", "imaginary": "x", "star": "b"}
PARAM_RE = re.compile(r"#(\d+)(?:\[[^\]]*\])?(%)?")
TAG_RE = re.compile(r"<[^>]+>")
ICON_FONT_PATH = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "hsr-icon.ttf"


def font(size: int, weight: str = "medium"):
    return HSRFonts.get_font(size, weight)  # type: ignore[arg-type]


@functools.lru_cache(maxsize=32)
def icon_font(size: int):
    return ImageFont.truetype(str(ICON_FONT_PATH), size)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("\\n", "\n").replace("<br>", "\n").replace("<br/>", "\n")
    text = TAG_RE.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def format_number(value: float | int | None) -> str:
    if value is None:
        return "?"
    number = float(value)
    if abs(number - round(number)) < 0.01:
        return f"{int(round(number)):,}"
    return f"{number:,.1f}"


def format_hp(value: float | int | None) -> str:
    if value is None:
        return "?"
    return f"{math.floor(float(value) + 0.5):,}"


def expand_params(text: str | None, params: Sequence[float | int]) -> str:
    """Expand bare/typed placeholders and convert percentage ratios for display."""
    clean = clean_text(text)
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(params):
            return ""
        value = float(params[index]) * (100 if match.group(2) else 1)
        rendered = f"{value:g}"
        return rendered + ("%" if match.group(2) else "")
    return re.sub(r"[ \t]+", " ", PARAM_RE.sub(replace, clean)).strip()


def mode_label(mode: GameMode) -> str:
    return MODE_NAMES[mode]


def canonical_mode(mode: GameMode | str) -> str:
    key = str(mode).strip().upper()
    if key not in MODE_CANONICAL:
        raise ValueError("game_mode must be one of MOC, PF, AS, or AA")
    return MODE_CANONICAL[key]


def normalize_floors(game_mode: GameMode | str, floors: Sequence[int] | int | None) -> list[int]:
    key = str(game_mode).strip().upper()
    if key not in DEFAULT_FLOORS and key != "AA":
        raise ValueError("game_mode must be one of MOC, PF, AS, or AA")
    if key == "AA":
        return [] if floors is None else sorted({int(floor) for floor in floors})
    if floors is None:
        return list(DEFAULT_FLOORS[key])
    values = [floors] if isinstance(floors, int) else list(floors)
    return sorted({int(floor) for floor in values})


@dataclass
class EndgameFloorCard:
    """One floor image with its source stage and optional rendered-cache path."""

    image: Image.Image
    floor: int
    stage_id: int | None = None
    name: str | None = None
    cache_path: Path | None = None

    def save(self, *args, **kwargs):
        """Save the image using the arguments accepted by PIL.Image.save."""
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.image, name)


@dataclass
class EndgameCardResult:
    """A season's floor cards and authoritative live-window metadata."""

    game_mode: str
    season_id: int
    season_name: str
    version: str
    cards: list[EndgameFloorCard] = field(default_factory=list)
    begins_at: datetime | None = None
    ends_at: datetime | None = None
    is_live: bool = False
    next_season_id: int | None = None

    @property
    def images(self) -> list[Image.Image]:
        return [card.image for card in self.cards]

    @property
    def start(self) -> datetime | None:
        return self.begins_at

    @property
    def end(self) -> datetime | None:
        return self.ends_at


@dataclass
class HpBar:
    amount: float
    phase: int | None = None


@dataclass
class CorrosionTarget:
    identifier: int
    name: str
    icon: Image.Image | None
    hp: float | None
    bonus_hp: float | None
    bonus_ratio: float | None
    icon_asset: str = ""


@dataclass
class MonsterInfo:
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
    client: NanokaClient
    status: str
    version: str
    begins_at: datetime | None
    ends_at: datetime | None
    element_icons: dict[str, Image.Image] = field(default_factory=dict)
    season_effects: list[EffectInfo] = field(default_factory=list)
    grit_effects: list[EffectInfo] = field(default_factory=list)




def parse_stage_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        levels = payload.get("level")
        if isinstance(levels, list):
            return [item for item in levels if isinstance(item, dict)]
        return [payload]
    return []


def group_floor_records(records: Sequence[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
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
    name = clean_text(record.get("name"))
    match = re.search(r"\(([IVXLCDM]+)\)\s*$", name)
    if match:
        value = roman_to_int(match.group(1))
        if value:
            return value
    return index


def roman_to_int(value: str) -> int | None:
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
    value = record.get("id")
    return int(value) if value is not None else None


def stage_from_record(record: dict[str, Any], mode: str = "maze") -> StageLevel:
    return StageLevel.model_validate({"mode": mode, **record})


def merge_stage(primary: StageLevel, extras: Sequence[StageLevel]) -> StageLevel:
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
    nodes: dict[int, list[StageEvent]] = {}
    if stage.event_id_list:
        nodes[3] = list(stage.event_id_list)
    if stage.event_id_list1:
        nodes[1] = list(stage.event_id_list1)
    if stage.event_id_list2:
        nodes[2] = list(stage.event_id_list2)
    return nodes


async def resolve_monster_record(client: NanokaClient, identifier: int) -> MonsterDetail | None:
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
    hard = await client.cache.load_json("HardLevelGroup.json", required=False) or []
    elite = await client.cache.load_json("EliteGroup.json", required=False) or []
    values = await client.cache.load_json("monstervalue.json", required=False) or {}
    return hard, elite, values


def find_ratio(rows: Sequence[dict[str, Any]], key: str, value: int | None) -> float:
    if value is None:
        return 1.0
    for row in rows:
        if int(row.get(key, -1)) == int(value):
            return float(row.get("HPRatio", 1) or 1)
    return 1.0


def raw_monster_phases(detail: MonsterDetail | None) -> list[dict[str, Any]]:
    if detail is None:
        return []
    payload = getattr(detail, "__pydantic_extra__", None) or {}
    phases = getattr(detail, "phase_list", None) or payload.get("phase_list")
    if isinstance(phases, list):
        return [phase for phase in phases if isinstance(phase, dict)]
    return []


def monster_hp_values(
    event: StageEvent,
    identifier: int,
    detail: MonsterDetail | None,
    hard_rows: Sequence[dict[str, Any]],
    elite_rows: Sequence[dict[str, Any]],
    values: dict[str, Any],
) -> list[HpBar]:
    stats = values.get(str(identifier)) or {}
    base = float((detail.hp_base if detail is not None else None) or stats.get("HPBase") or 0)
    if not base:
        return []
    variant_ratio = 1.0
    level = event.level
    if detail is not None:
        variant = next((entry for entry in detail.child if str(entry.id) == str(identifier)), None)
        if variant is None and detail.child:
            variant = detail.child[0]
        if variant is not None:
            variant_ratio = float(variant.hp_modify_ratio or 1)
    hard_ratio = 1.0
    for row in hard_rows:
        if int(row.get("HardLevelGroup", -1)) == int(event.hard_level_group or -1) and int(row.get("Level", -1)) == int(level or -1):
            hard_ratio = float(row.get("HPRatio", 1) or 1)
            break
    elite_ratio = find_ratio(elite_rows, "EliteGroup", event.elite_group)
    per_bar = base * hard_ratio * elite_ratio * variant_ratio
    phases = raw_monster_phases(detail)
    if not phases:
        return [HpBar(per_bar, None)]
    bars: list[HpBar] = []
    for index, phase in enumerate(phases, start=1):
        ratio = float(phase.get("phase_max_hp_ratio", 1) or 1)
        bars.append(HpBar(per_bar * ratio, int(phase.get("phase_num") or index)))
    return bars


def monster_asset(identifier: int, detail: MonsterDetail | None) -> str:
    """Use Nanoka's artwork stem; boss variants often share a base icon."""
    if detail is not None and detail.image_path:
        stem = Path(detail.image_path.replace("\\", "/")).stem
    else:
        stem = f"Monster_{detail.id if detail is not None else identifier}"
    return f"monstermiddleicon/{stem}.webp"



def season_status(schedule: MazeSchedule, now: datetime | None = None) -> str:
    """Classify only live windows; deployment dates do not imply live status."""
    moment = now or datetime.now(timezone.utc)
    if not schedule.has_live_window:
        return "UNSCHEDULED"
    start, end = schedule.live_begins_at, schedule.live_ends_at
    if start and start > moment:
        return "UPCOMING"
    if end and end < moment:
        return "ENDED"
    return "LIVE"


def format_date(value: datetime | None) -> str:
    return value.strftime("%d %b %Y") if value else "-"


def extract_stage_name(record: dict[str, Any], floor: int) -> str:
    name = clean_text(record.get("name"))
    if not name:
        return f"Floor {floor}"
    return re.sub(r"\s*\([IVXLCDM]+\)\s*$", "", name).strip()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, text_font) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            if lines:
                lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=text_font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def paste_icon(canvas: Image.Image, icon: Image.Image | None, box):
    if icon is None:
        return
    left, top, right, bottom = [int(value) for value in box]
    size = (max(1, right - left), max(1, bottom - top))
    working = ImageOps.contain(icon.convert("RGBA"), size, Image.Resampling.LANCZOS)
    x = left + (size[0] - working.width) // 2
    y = top + (size[1] - working.height) // 2
    canvas.alpha_composite(working, (x, y))


def load_icon(client: NanokaClient, relative: str) -> Image.Image | None:
    path = client.cache.asset_file(relative)
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGBA")
    except (OSError, ValueError):
        return None


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


def invasion_ratio(event: StageEvent) -> float | None:
    if event.invasion is None:
        return None
    params = getattr(event.invasion, "maze_buff_param", None) or []
    return float(params[1]) if len(params) > 1 else None


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
    """Resolve node waves, HP, corrosion, and effects for one logical floor."""
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
        elements=elements, client=client, status=status, version=client.version,
        begins_at=season.live_begins_at, ends_at=season.live_ends_at,
        season_effects=[EffectInfo.from_payload(item, expand_params) for item in season_payload.get("option", [])],
        grit_effects=[EffectInfo.from_payload(item, expand_params) for item in season_payload.get("sub_option", [])],
    )


def draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, fill) -> None:
    import math
    points = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        factor = 1.0 if index % 2 == 0 else 0.45
        points.append((cx + math.cos(angle) * radius * factor, cy + math.sin(angle) * radius * factor))
    draw.polygon(points, fill=fill)


def draw_chip(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    label: str,
    *,
    color=GOLD,
    size: int = 18,
) -> int:
    x, y = xy
    text_font = font(size, "bold")
    width = int(draw.textlength(label, font=text_font)) + 26
    rounded(draw, (x, y, x + width, y + 30), 15, (35, 31, 52, 255), (*color[:3], 120))
    draw.text((x + 13, y + 15), label, font=text_font, fill=color, anchor="lm")
    return width


def draw_element_chip(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    element: str,
    icons: dict[str, Image.Image],
) -> int:
    color = ELEMENT_COLORS.get(element, MUTED)
    label = ELEMENT_LABELS.get(element, element.title())
    text_font = font(17, "bold")
    width = int(draw.textlength(label, font=text_font)) + 44
    rounded(draw, (x, y, x + width, y + 30), 15, (31, 27, 47, 255), (*color[:3], 100))
    draw.text((x + 9, y + 15), ICON_GLYPHS.get(element, "b"), font=icon_font(19), fill=color, anchor="lm")
    draw.text((x + 33, y + 15), label, font=text_font, fill=color, anchor="lm")
    return width


NAME_FONT_SIZE = 19
HP_FONT_SIZE = 17
NAME_LINE_HEIGHT = 22
HP_LINE_HEIGHT = 23
CORROSION_LINE_HEIGHT = 19
CHIP_HEIGHT = 30
ROW_TOP_PAD = 8
ROW_BOTTOM_PAD = 8


def _measure_draw() -> ImageDraw.ImageDraw:
    canvas = Image.new("RGBA", (1, 1))
    return ImageDraw.Draw(canvas)


def wrapped_lines(text: str, width: int, size: int = NAME_FONT_SIZE) -> int:
    draw = _measure_draw()
    return max(1, len(wrap_text(draw, text, max(width, 1), font(size, "bold"))))


def _monster_lines(monster: MonsterInfo, width: int) -> list[tuple[str, Any, int]]:
    draw = _measure_draw()
    name = monster.name + (f"  x{monster.count}" if monster.count > 1 else "")
    lines = [(line, TEXT, 19) for line in wrap_text(draw, name, width, font(19, "bold"))]
    lines.extend((line, GOLD, 17) for line in wrap_text(draw, monster.hp_text, width, font(17, "bold")))
    if monster.corrosion_hp is not None and monster.corrosion_ratio:
        text = f"Voracity HP +{format_hp(monster.corrosion_hp)} ({monster.corrosion_ratio:.0%})"
        lines.extend((line, RED, 16) for line in wrap_text(draw, text, width, font(16, "bold")))
    return lines


def monster_row_height(monster: MonsterInfo, name_width: int) -> int:
    """Measure all enemy text and weakness icons without truncating names."""
    return max(80, sum(size + 5 for _, _, size in _monster_lines(monster, name_width)) + (28 if monster.weaknesses else 0) + 16)


def _effect_height(effects: Sequence[EffectInfo], width: int) -> int:
    draw = _measure_draw()
    return sum(
        14 + len(wrap_text(draw, effect.name, width, font(18, "bold"))) * 24
        + len(wrap_text(draw, effect.text, width, font(17))) * 23
        for effect in effects
    )


def _draw_effects(draw, x: int, y: int, width: int, effects: Sequence[EffectInfo]) -> int:
    start = y
    for effect in effects:
        y += 8
        for line in wrap_text(draw, effect.name, width, font(18, "bold")):
            draw.text((x, y), line, font=font(18, "bold"), fill=GOLD, anchor="lt")
            y += 24
        for line in wrap_text(draw, effect.text, width, font(17)):
            draw.text((x, y), line, font=font(17), fill=BODY, anchor="lt")
            y += 23
        y += 6
    return y - start


def _node_monster_height(node: NodeInfo, width: int) -> int:
    height = sum(28 + sum(monster_row_height(monster, width - 106) for monster in wave) for wave in node.waves)
    if node.corrosion_targets:
        draw = _measure_draw()
        height += 34
        for target in node.corrosion_targets:
            height += 30 + 23 * len(wrap_text(draw, target.name, width - 40, font(17, "bold")))
    return height


def node_panel_height(node: NodeInfo, width: int) -> int:
    """Measure enemies and effects with the same widths used for drawing."""
    split = width > 700 and bool(node.season_effects or node.stage_effects)
    monster_width = 410 if split else width
    effects_width = width - 450 if split else width - 36
    effects_height = sum(32 + _effect_height(effects, effects_width) for effects in (node.season_effects, node.stage_effects) if effects)
    enemies_height = _node_monster_height(node, monster_width)
    content = max(enemies_height, effects_height) if split else enemies_height + effects_height
    elements_height = 30 if node.elements else 0
    return 66 + elements_height + content + (46 if node.invasion_level else 0) + 12


def draw_node_panel(canvas, draw, x: int, y: int, width: int, node: NodeInfo, icons) -> int:
    """Draw one node, including Starward bosses and mode-specific effects."""
    height = node_panel_height(node, width)
    rounded(draw, (x, y, x + width, y + height), 18, PANEL, EDGE)
    draw.text((x + 18, y + 20), node.label or f"NODE {node.number}", font=font(20, "bold"), fill=GOLD, anchor="lm")
    if node.level:
        draw.text((x + width - 18, y + 20), f"Lv. {node.level}", font=font(17, "bold"), fill=MUTED, anchor="rm")
    cursor = y + 46
    if node.elements:
        draw.text((x + 18, cursor), "RECOMMENDED", font=font(12, "bold"), fill=MUTED, anchor="lt")
        for index, element in enumerate(node.elements):
            draw.text((x + 144 + 30 * index, cursor - 3), ICON_GLYPHS.get(element, "b"), font=icon_font(23), fill=ELEMENT_COLORS.get(element, MUTED), anchor="lt")
        cursor += 30
    content_top = cursor
    split = width > 700 and bool(node.season_effects or node.stage_effects)
    monster_width = 410 if split else width
    for wave_index, wave in enumerate(node.waves, start=1):
        draw.text((x + 18, cursor), f"WAVE {wave_index}", font=font(14, "bold"), fill=MUTED, anchor="lt")
        cursor += 28
        for monster in wave:
            paste_icon(canvas, monster.icon, (x + 18, cursor, x + 80, cursor + 72))
            line_y = cursor + 5
            for text, color, size in _monster_lines(monster, monster_width - 106):
                draw.text((x + 90, line_y), text, font=font(size, "bold"), fill=color, anchor="lt")
                line_y += size + 5
            for index, weakness in enumerate(monster.weaknesses):
                draw.text((x + 90 + 29 * index, line_y), ICON_GLYPHS.get(weakness, "b"), font=icon_font(22), fill=ELEMENT_COLORS.get(weakness, MUTED), anchor="lt")
            cursor += monster_row_height(monster, monster_width - 106)
    if node.corrosion_targets:
        draw.text((x + 18, cursor + 8), "ADDITIONAL CORROSION TARGETS", font=font(14, "bold"), fill=RED, anchor="lt")
        cursor += 34
        for target in node.corrosion_targets:
            for line in wrap_text(draw, target.name, monster_width - 40, font(17, "bold")):
                draw.text((x + 20, cursor), line, font=font(17, "bold"), fill=BODY, anchor="lt")
                cursor += 23
            draw.text((x + 20, cursor), f"Voracity HP +{format_hp(target.bonus_hp)} ({target.bonus_ratio:.0%})", font=font(16, "bold"), fill=RED, anchor="lt")
            cursor += 30
    effects_x = x + 430 if split else x + 18
    effects_y = content_top if split else cursor
    effects_width = width - 450 if split else width - 36
    for title, effects in (("SEASON EFFECTS", node.season_effects), ("STAGE EFFECTS", node.stage_effects)):
        if effects:
            draw.text((effects_x, effects_y + 7), title, font=font(14, "bold"), fill=CYAN, anchor="lt")
            effects_y += 32
            effects_y += _draw_effects(draw, effects_x, effects_y, effects_width, effects)
    if node.invasion_level:
        rounded(draw, (x + 14, y + height - 46, x + width - 14, y + height - 12), 12, (53, 27, 38, 255), (132, 59, 67, 255))
        ratio = f"  /  +{node.corrosion_ratio:.0%} HP" if node.corrosion_ratio else ""
        draw.text((x + 26, y + height - 29), f"VORACITY CORROSION Lv. {node.invasion_level}{ratio}", font=font(15, "bold"), fill=RED, anchor="lm")
    return height


def render_floor_card(data: FloorCardData) -> Image.Image:
    """Render a measured floor layout with every wave and effect visible."""
    inner_width = W - 2 * M
    column_width = (inner_width - GAP) // 2
    # Build each block separately so long effects never overlap the next panel.
    blocks: list[Image.Image] = []
    def text_panel(title: str, effects: Sequence[EffectInfo], color=CYAN):
        height = 60 + _effect_height(effects, inner_width - 44)
        panel = Image.new("RGBA", (inner_width, height), BG)
        draw = ImageDraw.Draw(panel)
        rounded(draw, (0, 0, inner_width - 1, height - 1), 18, PANEL, EDGE)
        draw.text((22, 18), title, font=font(15, "bold"), fill=color, anchor="lt")
        _draw_effects(draw, 22, 44, inner_width - 44, effects)
        blocks.append(panel)

    header_draw = _measure_draw()
    title_lines = wrap_text(header_draw, data.season_name or data.stage_name, inner_width, font(36, "bold"))
    stage_lines = wrap_text(header_draw, data.stage_name, inner_width - 180, font(19, "bold"))
    header = Image.new("RGBA", (inner_width, 142 + len(title_lines) * 44 + max(0, len(stage_lines) - 1) * 25), BG)
    draw = ImageDraw.Draw(header)
    draw.text((0, 0), mode_label(data.mode), font=font(21, "bold"), fill=PURPLE, anchor="lt")
    color = LIVE if data.status == "LIVE" else UPCOMING if data.status == "UPCOMING" else ENDED
    badge_width = int(draw.textlength(data.status, font=font(16, "bold"))) + 26
    draw_chip(draw, (inner_width - badge_width, 0), data.status, color=color, size=16)
    y = 48
    for line in title_lines:
        draw.text((0, y), line, font=font(36, "bold"), fill=TEXT, anchor="lt")
        y += 44
    y += 12
    draw.text((0, y), f"FLOOR {data.floor}", font=font(26, "bold"), fill=GOLD, anchor="lt")
    for line in stage_lines:
        draw.text((180, y + 3), line, font=font(19, "bold"), fill=BODY, anchor="lt")
        y += 25
    draw.text((0, y + 22), f"{format_date(data.begins_at)} - {format_date(data.ends_at)}", font=font(16, "bold"), fill=MUTED, anchor="lt")
    blocks.append(header)
    if data.buff_text:
        text_panel("SEASON BUFF", [EffectInfo(data.buff_name, data.buff_text)], GOLD)
    if data.conditions or data.special:
        text_panel("CLEAR CONDITIONS", [EffectInfo("", "\n".join([*data.conditions, *([data.special] if data.special else [])]))])
    if data.season_effects:
        text_panel("SEASON OPTIONS", data.season_effects, PURPLE)
    if data.grit_effects:
        text_panel("GRIT EFFECTS", data.grit_effects, PURPLE)
    if data.mode == "AS":
        groups = [[node] for node in data.nodes]
    else:
        groups = [[node for node in data.nodes if node.number in (1, 2)]]
        groups.extend([node] for node in data.nodes if node.number not in (1, 2))
    for group in groups:
        if not group:
            continue
        width = column_width if len(group) == 2 else inner_width
        height = max(node_panel_height(node, width) for node in group)
        panel = Image.new("RGBA", (inner_width, height), BG)
        draw = ImageDraw.Draw(panel)
        for index, node in enumerate(group):
            draw_node_panel(panel, draw, index * (width + GAP), 0, width, node, data.element_icons)
        blocks.append(panel)
    height = M + sum(block.height for block in blocks) + GAP * len(blocks) + 52
    canvas = Image.new("RGBA", (W, height), BG)
    y = M
    for block in blocks:
        canvas.alpha_composite(block, (M, y))
        y += block.height + GAP
    draw = ImageDraw.Draw(canvas)
    draw.line((M, height - 44, W - M, height - 44), fill=EDGE, width=1)
    draw.text((M, height - 23), "HSR  /  NANOKA", font=font(15, "bold"), fill=MUTED, anchor="lm")
    draw.text((W - M, height - 23), f"{data.mode}  /  {data.season.id}  /  F{data.floor}", font=font(15, "bold"), fill=MUTED, anchor="rm")
    return canvas



async def _load_assets(data: FloorCardData) -> None:
    entries = [monster for node in data.nodes for wave in node.waves for monster in wave]
    entries.extend(target for node in data.nodes for target in node.corrosion_targets)
    missing = {entry.icon_asset for entry in entries if entry.icon is None and entry.icon_asset}
    await asyncio.gather(*(data.client.fetch_asset(relative) for relative in missing))
    for entry in entries:
        if entry.icon is None and entry.icon_asset:
            entry.icon = load_icon(data.client, entry.icon_asset)


def _cache_name(mode: GameMode, season_id: int, floor: int, status: str) -> str:
    # Schedule badges must change when an upcoming season goes live.
    return f"ENDGAME_v2_{mode}_{season_id}_F{floor}_{status}"


async def _season_card(
    game_mode: GameMode,
    season: MazeSchedule,
    floors: Sequence[int] | int | None,
    *,
    locale: str,
    cache_dir: str | Path | None,
    proxy: str | None,
    rendered_cache_dir: str | Path | None,
    use_rendered_cache: bool,
    force_refresh: bool,
) -> EndgameCardResult:
    if game_mode == "AA":
        raise NotImplementedError("Anomaly Arbitration cards are deferred until live schedules are available.")
    canonical = canonical_mode(game_mode)
    client = NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        await client._prepare()
        payload = await client._detail(canonical, season.id) if season.id is not None else None
        records = parse_stage_records(payload)
        if not records:
            raise ValueError(f"No stage data found for {game_mode} season {season.id}")
        grouped = group_floor_records(records)
        requested = normalize_floors(game_mode, floors) or sorted(grouped)
        missing = [floor for floor in requested if floor not in grouped]
        if missing:
            raise ValueError(f"{game_mode} season {season.id} has no floor(s): {', '.join(map(str, missing))}")
        status = season_status(season)
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        cards: list[EndgameFloorCard] = []
        for floor in requested:
            floor_records = grouped[floor]
            cached = None if force_refresh else cache.load(_cache_name(game_mode, season.id, floor, status), "endgame", client.version, locale=locale)
            cache_path = cache.path(_cache_name(game_mode, season.id, floor, status), "endgame", client.version, locale=locale)
            if cached is not None:
                stage_id = stage_identifier(floor_records[0])
                cards.append(EndgameFloorCard(cached, floor=floor, stage_id=stage_id, name=extract_stage_name(floor_records[0], floor), cache_path=cache_path))
                continue
            floor_data = await build_floor_data(client, season, floor, floor_records, mode=game_mode, status=status,
                season_payload=payload if isinstance(payload, dict) else None)
            await _load_assets(floor_data)
            image = await asyncio.to_thread(render_floor_card, floor_data)
            if use_rendered_cache:
                cache_path = cache.save(image, _cache_name(game_mode, season.id, floor, status), "endgame", client.version, locale=locale)
            cards.append(EndgameFloorCard(image, floor=floor, stage_id=stage_identifier(floor_records[0]), name=floor_data.stage_name, cache_path=cache_path))
        return EndgameCardResult(
            game_mode=game_mode, season_id=season.id, season_name=(payload.get("name") if isinstance(payload, dict) else None) or extract_stage_name(records[0], 1),
            version=client.version, cards=cards, begins_at=season.live_begins_at, ends_at=season.live_ends_at,
            is_live=season.is_live,
        )
    finally:
        await client.close()


async def get_current_endgame_card(
    game_mode: GameMode = "MOC",
    floors: Sequence[int] | int | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> EndgameCardResult:
    """Render live endgame floor cards, one image per requested floor.

    MOC defaults to floors 11 and 12; PF and AS default to 3 and 4.
    AA raises ``NotImplementedError`` pending reliable live schedules.
    """
    locale = normalize_locale(locale)
    game_mode = str(game_mode).strip().upper()  # type: ignore[assignment]
    canonical_mode(game_mode)
    if game_mode == "AA":
        raise NotImplementedError("Anomaly Arbitration cards are deferred until live schedules are available.")
    client = NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        season = await client.get_current_endgame(canonical_mode(game_mode))
        if season is None or not season.schedule.has_live_window or not season.schedule.is_live:
            raise ValueError(f"No live {game_mode} season is available")
        result = await _season_card(
            game_mode, season.schedule, floors, locale=locale, cache_dir=cache_dir, proxy=proxy,
            rendered_cache_dir=rendered_cache_dir, use_rendered_cache=use_rendered_cache,
            force_refresh=force_refresh,
        )
        return result
    finally:
        await client.close()


async def get_next_endgame_card(
    game_mode: GameMode = "MOC",
    floors: Sequence[int] | int | None = None,
    *,
    look_ahead: int | Literal["max"] = 1,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> EndgameCardResult | list[EndgameCardResult]:
    """Render upcoming endgame cards after the live season.

    ``look_ahead=1`` returns one result. Larger values and ``"max"`` return a
    list ordered by live start time. Published seasons without a live window
    follow dated seasons and show ``UNSCHEDULED`` with no live dates.
    AA raises ``NotImplementedError``.
    """
    locale = normalize_locale(locale)
    game_mode = str(game_mode).strip().upper()  # type: ignore[assignment]
    canonical_mode(game_mode)
    if game_mode == "AA":
        raise NotImplementedError("Anomaly Arbitration cards are deferred until live schedules are available.")
    if look_ahead != "max" and int(look_ahead) < 1:
        raise ValueError("look_ahead must be at least 1 or 'max'")
    client = NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        canonical = canonical_mode(game_mode)
        items = await client.list_maze(mode=canonical, include_future=True)
        now = datetime.now(timezone.utc)
        started_ids = [item.id for item in items if item.has_live_window and item.live_begins_at <= now]
        anchor = max(started_ids) if started_ids else None
        later = [
            item for item in items
            if (anchor is None or item.id > anchor)
            and (not item.has_live_window or item.live_begins_at > now)
        ]
        later.sort(key=lambda item: (
            item.live_begins_at or datetime.max.replace(tzinfo=timezone.utc), item.id,
        ))
        results: list[EndgameCardResult] = []
        for season in later:
            try:
                result = await _season_card(
                    game_mode, season, floors, locale=locale, cache_dir=cache_dir, proxy=proxy,
                    rendered_cache_dir=rendered_cache_dir, use_rendered_cache=use_rendered_cache,
                    force_refresh=force_refresh,
                )
            except (ValueError, NanokaNotFoundError):
                continue
            results.append(result)
            if look_ahead != "max" and len(results) >= int(look_ahead):
                break
        if look_ahead == 1:
            if not results:
                raise ValueError(f"No upcoming {game_mode} season with stage data is available")
            return results[0]
        return results
    finally:
        await client.close()


__all__ = ["EndgameCardResult", "EndgameFloorCard", "get_current_endgame_card", "get_next_endgame_card"]
