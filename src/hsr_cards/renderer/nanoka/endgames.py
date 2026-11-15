"""Telegram-friendly Memory of Chaos endgame info cards.

The first pass is intentionally MOC-only.  The public API is shaped so Pure
Fiction, Apocalyptic Shadow, and Anomaly Arbitration can use the same floor
card pipeline later without changing the client-facing arguments.
"""

from __future__ import annotations

import asyncio
import functools
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import MazeSchedule, MonsterDetail, StageEvent, StageLevel
from ...utils.hsrfonts import HSRFonts
from .data import RenderedCardCache, normalize_locale

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
PARAM_RE = re.compile(r"#(\d+)\[[^\]]*\](%)?")
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
    return f"{round(float(value)):,}"


def expand_params(text: str | None, params: Sequence[float | int]) -> str:
    clean = clean_text(text)
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(params):
            return ""
        value = params[index]
        rendered = format_number(value) if index == -1 else str(int(value)) if float(value).is_integer() else f"{value:g}"
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
    image: Image.Image
    floor: int
    stage_id: int | None = None
    name: str | None = None
    cache_path: Path | None = None

    def save(self, *args, **kwargs):
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.image, name)


@dataclass
class EndgameCardResult:
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
    continuation = extras[-1]
    payload = primary.model_dump()
    payload["challenge"] = [item.model_dump() for item in continuation.challenge] or payload.get("challenge", [])
    payload["challenge_special"] = [item.model_dump() for item in continuation.challenge_special] or payload.get("challenge_special", [])
    payload["event_id_list"] = [item.model_dump() for item in continuation.event_id_list] or payload.get("event_id_list", [])
    payload["countdown"] = continuation.countdown or payload.get("countdown")
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
    base_id = detail.id if detail is not None else identifier
    return f"monstermiddleicon/Monster_{base_id}.webp"



def season_status(schedule: MazeSchedule, now: datetime | None = None) -> str:
    moment = now or datetime.now(schedule.begins_at.tzinfo if schedule.begins_at else None)
    start, end = schedule.begins_at, schedule.ends_at
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
    weaknesses = [weakness.lower() for weakness in (detail.weaknesses if detail else [])]
    bars = monster_hp_values(event, identifier, detail, hard_rows, elite_rows, values)
    hp = bars[0].amount if bars else None
    icon = load_icon(client, monster_asset(identifier, detail))
    corrosion_hp = None
    if corrosion_ratio and bars:
        corrosion_hp = bars[0].amount * corrosion_ratio
    return MonsterInfo(
        identifier=identifier, name=name, icon=icon, hp=hp, weaknesses=weaknesses,
        hp_bars=bars, corrosion_ratio=corrosion_ratio, corrosion_hp=corrosion_hp,
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
) -> FloorCardData:
    primary_record = records[0]
    stage_records = [stage_from_record(record) for record in records]
    stage = merge_stage(stage_records[0], stage_records[1:])
    hard_rows, elite_rows, values = await hp_resolver(client)
    nodes: list[NodeInfo] = []
    for number, events in sorted(stage_events_by_node(stage).items()):
        event = events[0]
        ratio = invasion_ratio(event)
        affected = set(event.invasion.all_monster_ids) if event.invasion is not None else set()
        waves: list[list[MonsterInfo]] = []
        for slot in event.monster_list:
            wave = []
            for identifier in slot.monster_ids:
                wave.append(await load_monster_info(
                    client, event, identifier, hard_rows, elite_rows, values,
                    corrosion_ratio=ratio if identifier in affected else None,
                ))
            if wave:
                waves.append(wave)
        targets: list[CorrosionTarget] = []
        if event.invasion is not None:
            for slot in event.invasion.monster_list:
                identifier = getattr(slot, "monster_id", None) or getattr(slot, "resolved_id", None)
                if identifier is None:
                    identifier = next(iter(getattr(slot, "monster_ids", [])), None)
                if identifier is None:
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
                    bonus_ratio=ratio,
                ))
        nodes.append(NodeInfo(
            number=number,
            level=event.level,
            waves=waves,
            invasion_level=event.invasion.level if event.invasion else None,
            corrosion_ratio=ratio,
            corrosion_desc=clean_text(event.invasion.desc) if event.invasion else None,
            corrosion_targets=targets,
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
    buff_name = f"{season.display_name() or 'Memory of Chaos'}  /  Stage {floor}"
    buff_text = expand_params(primary_record.get("desc"), primary_record.get("param") or primary_record.get("param_list") or [])
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
        season_name=season.display_name() or extract_stage_name(primary_record, floor),
        buff_name=buff_name,
        buff_text=buff_text, conditions=conditions, special=special, nodes=nodes,
        elements=elements, client=client, status=status, version=client.version,
        begins_at=season.begins_at, ends_at=season.ends_at,
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


def monster_row_height(monster: MonsterInfo, name_width: int) -> int:
    name_lines = wrapped_lines(monster.name, name_width)
    hp_width = name_width
    draw = _measure_draw()
    hp_single = draw.textlength(monster.hp_text, font=font(HP_FONT_SIZE, "bold")) <= hp_width
    hp_height = HP_LINE_HEIGHT if hp_single else HP_LINE_HEIGHT + 18
    extra = CORROSION_LINE_HEIGHT if monster.corrosion_hp is not None and monster.corrosion_ratio else 0
    chips = CHIP_HEIGHT + 4 if monster.weaknesses else 0
    return ROW_TOP_PAD + name_lines * NAME_LINE_HEIGHT + hp_height + extra + chips + ROW_BOTTOM_PAD


def node_panel_height(node: NodeInfo, width: int) -> int:
    name_width = width - 108
    wave_height = sum(
        22 + sum(monster_row_height(monster, name_width) for monster in wave)
        for wave in node.waves
    )
    target_height = 0
    if node.corrosion_targets:
        target_height = 52 + 46 * len(node.corrosion_targets)
    return 52 + wave_height + target_height + (38 if node.invasion_level else 0)


def draw_hp_line(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    monster: MonsterInfo,
    width: int,
) -> int:
    hp_text = monster.hp_text
    hp_font = font(HP_FONT_SIZE, "bold")
    if draw.textlength(hp_text, font=hp_font) <= width:
        draw.text((x, y), hp_text, font=hp_font, fill=GOLD, anchor="lm")
        return HP_LINE_HEIGHT
    draw.text((x, y), "HP", font=font(HP_FONT_SIZE, "bold"), fill=GOLD, anchor="lm")
    offset = x
    for index, bar in enumerate(monster.hp_bars, start=1):
        label = f"P{bar.phase or index} {format_hp(bar.amount)}"
        if index > 1:
            label = "/ " + label
        draw.text((offset, y + 20), label, font=font(16, "bold"), fill=GOLD, anchor="lm")
        offset += int(draw.textlength(label, font=font(16, "bold"))) + 8
    return HP_LINE_HEIGHT + 18


def draw_node_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    node: NodeInfo,
    icons: dict[str, Image.Image],
) -> int:
    height = node_panel_height(node, width)
    rounded(draw, (x, y, x + width, y + height), 18, PANEL, EDGE)
    draw.text((x + 18, y + 20), f"NODE {node.number}", font=font(20, "bold"), fill=GOLD, anchor="lm")
    if node.level:
        draw.text((x + width - 18, y + 20), f"Lv. {node.level}", font=font(17, "bold"), fill=MUTED, anchor="rm")
    cursor = y + 46
    for wave_index, wave in enumerate(node.waves, start=1):
        draw.text((x + 18, cursor), f"WAVE {wave_index}", font=font(14, "bold"), fill=MUTED, anchor="lm")
        cursor += 14
        for monster in wave:
            icon_size = 62
            paste_icon(canvas, monster.icon, (x + 18, cursor, x + 18 + icon_size, cursor + 72))
            name_x = x + 90
            name_width = width - 108
            name_lines = wrap_text(draw, monster.name, name_width, font(NAME_FONT_SIZE, "bold"))[:2]
            line_y = cursor + ROW_TOP_PAD
            for line in name_lines:
                draw.text((name_x, line_y), line, font=font(NAME_FONT_SIZE, "bold"), fill=TEXT, anchor="lm")
                line_y += NAME_LINE_HEIGHT
            line_y += draw_hp_line(draw, name_x, line_y + 2, monster, name_width)
            if monster.corrosion_hp is not None and monster.corrosion_ratio:
                bonus = f"Voracity HP +{format_hp(monster.corrosion_hp)} ({monster.corrosion_ratio:.0%})"
                draw.text((name_x, line_y), bonus, font=font(16, "bold"), fill=RED, anchor="lm")
                line_y += CORROSION_LINE_HEIGHT
            weak_x = name_x
            weak_y = line_y + 2
            for weakness in monster.weaknesses[:4]:
                weak_x += draw_element_chip(canvas, draw, weak_x, weak_y, weakness, icons) + 6
            cursor += monster_row_height(monster, name_width)
        cursor += 2
    if node.corrosion_targets:
        cursor += 14
        draw.text((x + 18, cursor), "ADDITIONAL CORROSION TARGETS", font=font(14, "bold"), fill=RED, anchor="lm")
        cursor += 24
        for target in node.corrosion_targets:
            paste_icon(canvas, target.icon, (x + 20, cursor, x + 48, cursor + 32))
            draw.text((x + 56, cursor + 8), target.name, font=font(16, "bold"), fill=BODY, anchor="lm")
            bonus = format_hp(target.bonus_hp) if target.bonus_hp is not None else "?"
            draw.text((x + width - 18, cursor + 8), f"Voracity HP +{bonus}", font=font(16, "bold"), fill=RED, anchor="rm")
            draw.text((x + 56, cursor + 26), f"({target.bonus_ratio:.0%} of Max HP)", font=font(14, "bold"), fill=MUTED, anchor="lm")
            cursor += 46
    if node.invasion_level:
        rounded(draw, (x + 14, y + height - 46, x + width - 14, y + height - 12), 12, (53, 27, 38, 255), (132, 59, 67, 255))
        ratio = f"  -  +{node.corrosion_ratio:.0%} HP" if node.corrosion_ratio else ""
        draw.text((x + 26, y + height - 29), f"VORACITY CORROSION Lv. {node.invasion_level}{ratio}", font=font(15, "bold"), fill=RED, anchor="lm")
    return height


def render_floor_card(data: FloorCardData) -> Image.Image:
    column_width = (W - 2 * M - 18) // 2
    body_height = 0
    if data.nodes:
        top = [node for node in data.nodes if node.number in (1, 2)]
        if top:
            body_height += max(node_panel_height(node, column_width) for node in top) + GAP
        body_height += sum(node_panel_height(node, W - 2 * M) + GAP for node in data.nodes if node.number not in (1, 2))
    height_hint = max(1400, 860 + body_height)
    canvas = Image.new("RGBA", (W, height_hint), BG)
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle((0, 0, W, 132), fill=BG2)
    draw.text((M, 38), mode_label(data.mode), font=font(21, "bold"), fill=PURPLE, anchor="la")
    status_color = LIVE if data.status == "LIVE" else UPCOMING if data.status == "UPCOMING" else ENDED
    draw_chip(draw, (W - M - 96, 29), data.status, color=status_color, size=16)
    title_lines = wrap_text(draw, data.season_name or data.stage_name, W - 2 * M - 20, font(36, "bold"))
    y = 74
    for line in title_lines[:2]:
        draw.text((M, y), line, font=font(36, "bold"), fill=TEXT, anchor="la")
        y += 42
    draw.text((M, y + 6), f"FLOOR {data.floor}", font=font(26, "bold"), fill=GOLD, anchor="la")
    draw.text((M + 152, y + 11), data.stage_name, font=font(19, "bold"), fill=BODY, anchor="la")
    draw.text((W - M, y + 10), f"{format_date(data.begins_at)} - {format_date(data.ends_at)}", font=font(16, "bold"), fill=MUTED, anchor="ra")
    y += 52
    rounded(draw, (M, y, W - M, y + 142), 18, PANEL2, (93, 72, 132, 255))
    draw.text((M + 22, y + 23), "SEASON BUFF", font=font(15, "bold"), fill=GOLD, anchor="lm")
    draw.text((M + 22, y + 50), data.buff_name, font=font(20, "bold"), fill=GOLD, anchor="lm")
    buff_lines = wrap_text(draw, data.buff_text, W - 2 * M - 44, font(18, "bold"))[:3]
    line_y = y + 78
    for line in buff_lines:
        draw.text((M + 22, line_y), line, font=font(18, "bold"), fill=BODY, anchor="lm")
        line_y += 23
    y += 164
    condition_height = 58 + max(1, len(data.conditions) + (1 if data.special else 0)) * 28
    rounded(draw, (M, y, W - M, y + condition_height), 18, PANEL, EDGE)
    draw.text((M + 22, y + 22), "CLEAR CONDITIONS", font=font(15, "bold"), fill=CYAN, anchor="lm")
    cy = y + 48
    for condition in data.conditions:
        draw.ellipse((M + 24, cy - 3, M + 31, cy + 4), fill=CYAN)
        draw.text((M + 44, cy), condition, font=font(17, "bold"), fill=BODY, anchor="lm")
        cy += 28
    if data.special:
        draw_star(draw, M + 27, cy, 8, GOLD)
        draw.text((M + 44, cy), data.special, font=font(17, "bold"), fill=GOLD, anchor="lm")
    y += condition_height + GAP
    rounded(draw, (M, y, W - M, y + 50), 16, PANEL, EDGE)
    draw.text((M + 22, y + 25), "RECOMMENDED ELEMENTS", font=font(15, "bold"), fill=PURPLE, anchor="lm")
    ex = M + 280
    for element in data.elements:
        ex += draw_element_chip(canvas, draw, ex, y + 10, element, data.element_icons) + 8
    y += 68
    draw.text((M, y), "ENEMY WAVES", font=font(24, "bold"), fill=TEXT, anchor="la")
    y += 38
    top_nodes = [node for node in data.nodes if node.number in (1, 2)]
    bottom_nodes = [node for node in data.nodes if node.number not in (1, 2)]
    if top_nodes:
        column_gap = 18
        column_width = (W - 2 * M - column_gap) // 2
        for index, node in enumerate(top_nodes[:2]):
            draw_node_panel(canvas, draw, M + index * (column_width + column_gap), y, column_width, node, data.element_icons)
        y += max(node_panel_height(node, column_width) for node in top_nodes[:2]) + GAP
    for node in bottom_nodes:
        y += draw_node_panel(canvas, draw, M, y, W - 2 * M, node, data.element_icons) + GAP
    height = y + 52
    canvas = canvas.crop((0, 0, W, height))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.line((M, height - 44, W - M, height - 44), fill=EDGE, width=1)
    draw.text((M, height - 23), "HSR  /  NANOKA", font=font(15, "bold"), fill=MUTED, anchor="lm")
    draw.text((W - M, height - 23), f"{data.mode}  /  {data.season.id}  /  F{data.floor}", font=font(15, "bold"), fill=MUTED, anchor="rm")
    return canvas



async def _load_assets(data: FloorCardData) -> None:
    for node in data.nodes:
        for wave in node.waves:
            for monster in wave:
                if monster.icon is None:
                    monster.icon = load_icon(data.client, f"monstermiddleicon/Monster_{monster.identifier}.webp")
    for element in data.elements:
        icon = load_icon(data.client, f"element/{element}.webp")
        if icon is not None:
            data.element_icons[element] = icon


def _cache_name(mode: GameMode, season_id: int, floor: int) -> str:
    return f"ENDGAME_{mode}_{season_id}_F{floor}"


async def _season_card(
    game_mode: GameMode,
    season: MazeSchedule,
    floors: Sequence[int] | None,
    *,
    locale: str,
    cache_dir: str | Path | None,
    proxy: str | None,
    rendered_cache_dir: str | Path | None,
    use_rendered_cache: bool,
    force_refresh: bool,
) -> EndgameCardResult:
    if game_mode in {"PF", "AS", "AA"}:
        raise NotImplementedError("Endgame cards are currently implemented for MOC only.")
    canonical = canonical_mode(game_mode)
    client = NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        await client._prepare()
        payload = await client._detail("maze", season.id) if season.id is not None else None
        records = parse_stage_records(payload)
        if not records:
            raise ValueError(f"No stage data found for {game_mode} season {season.id}")
        grouped = group_floor_records(records)
        requested = normalize_floors(game_mode, floors) or sorted(grouped)
        missing = [floor for floor in requested if floor not in grouped]
        if missing:
            raise ValueError(f"MOC season {season.id} has no floor(s): {', '.join(map(str, missing))}")
        status = season_status(season)
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        cards: list[EndgameFloorCard] = []
        for floor in requested:
            floor_records = grouped[floor]
            cached = None if force_refresh else cache.load(_cache_name(game_mode, season.id, floor), "endgame", client.version, locale=locale)
            cache_path = cache.path(_cache_name(game_mode, season.id, floor), "endgame", client.version, locale=locale)
            if cached is not None:
                stage_id = stage_identifier(floor_records[0])
                cards.append(EndgameFloorCard(cached, floor=floor, stage_id=stage_id, name=clean_text(floor_records[0].get("name")), cache_path=cache_path))
                continue
            floor_data = await build_floor_data(client, season, floor, floor_records, mode=game_mode, status=status)
            await _load_assets(floor_data)
            image = await asyncio.to_thread(render_floor_card, floor_data)
            if use_rendered_cache:
                cache_path = cache.save(image, _cache_name(game_mode, season.id, floor), "endgame", client.version, locale=locale)
            cards.append(EndgameFloorCard(image, floor=floor, stage_id=stage_identifier(floor_records[0]), name=floor_data.stage_name, cache_path=cache_path))
        return EndgameCardResult(
            game_mode=game_mode, season_id=season.id, season_name=season.display_name() or "",
            version=client.version, cards=cards, begins_at=season.begins_at, ends_at=season.ends_at,
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

    MOC defaults to floors 11 and 12. PF and AS default to 3 and 4, and AA
    uses every published floor. Only MOC is implemented in this first pass.
    """
    locale = normalize_locale(locale)
    game_mode = str(game_mode).upper()  # type: ignore[assignment]
    if game_mode != "MOC":
        raise NotImplementedError("Endgame cards are currently implemented for MOC only.")
    client = NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        season = await client.get_current_endgame(canonical_mode(game_mode))
        if season is None:
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
    list ordered by live start time.
    """
    locale = normalize_locale(locale)
    game_mode = str(game_mode).upper()  # type: ignore[assignment]
    if game_mode != "MOC":
        raise NotImplementedError("Endgame cards are currently implemented for MOC only.")
    if look_ahead != "max" and int(look_ahead) < 1:
        raise ValueError("look_ahead must be at least 1 or 'max'")
    client = NanokaClient(language=locale, cache_dir=cache_dir, proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        canonical = canonical_mode(game_mode)
        current = await client.get_current_endgame(canonical)
        items = await client.list_maze(mode=canonical, include_future=True)
        later = [item for item in items if current is None or item.id != current.id]
        if current is not None and current.begins_at is not None:
            later = [item for item in later if item.begins_at is None or item.begins_at > current.begins_at]
        later = sorted(later, key=lambda item: (item.begins_at or datetime.max.replace(tzinfo=current.begins_at.tzinfo if current and current.begins_at else None), item.id))
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
        return results[0] if look_ahead == 1 else results
    finally:
        await client.close()


__all__ = ["EndgameCardResult", "EndgameFloorCard", "get_current_endgame_card", "get_next_endgame_card"]
