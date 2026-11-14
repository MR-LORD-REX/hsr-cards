"""Readable, level-80 Light Cone cards with inline S1-S5 values."""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageOps

from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import LightConeDetail
from ...utils.hsrfonts import HSRFonts
from .character_info import clean_localized, font as localized_font, make_star, material_name
from .data import RenderedCardCache, normalize_locale, parse_versions

W, MIN_H, M = 1080, 1440, 48
BODY_SIZE, LINE_H = 32, 44
BG = (12, 9, 22, 255)
PANEL = (27, 22, 42, 255)
EDGE = (67, 54, 91, 255)
TEXT = (241, 237, 249, 255)
MUTED = (182, 173, 204, 255)
GOLD = (255, 204, 119, 255)
PURPLE = (198, 169, 255, 255)
CYAN = (153, 226, 234, 255)
GREEN = (145, 234, 174, 255)
REMOVED = (237, 155, 170, 255)
PARAM_RE = re.compile(r"#(\d+)\[[^\]]*\](%)?")
RICH_RE = re.compile(r'\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*%?|"[^"\n]+"|“[^”\n]+”')

PATH_LABELS = {
    "en": {"warlock": "Nihility", "knight": "Preservation", "rogue": "The Hunt", "mage": "Erudition", "shaman": "Harmony", "priest": "Abundance", "warrior": "Destruction", "memory": "Remembrance", "elation": "Elation"},
    "zh": {"warlock": "虚无", "knight": "存护", "rogue": "巡猎", "mage": "智识", "shaman": "同谐", "priest": "丰饶", "warrior": "毁灭", "memory": "记忆", "elation": "欢愉"},
    "ja": {"warlock": "虚無", "knight": "存護", "rogue": "巡狩", "mage": "知恵", "shaman": "調和", "priest": "豊穣", "warrior": "壊滅", "memory": "記憶", "elation": "愉悦"},
    "ko": {"warlock": "공허", "knight": "보존", "rogue": "수렵", "mage": "지식", "shaman": "화합", "priest": "풍요", "warrior": "파멸", "memory": "기억", "elation": "환락"},
}

LABELS = {
    "en": ("LIGHT CONE", "MAX LEVEL 80", "SUPERIMPOSITION", "ASCENSION MATERIALS", "LV. 1 - 80", "Base HP", "Base ATK", "Base DEF"),
    "zh": ("光锥", "最高等级 80", "叠影", "晋阶材料", "等级 1 - 80", "基础生命值", "基础攻击力", "基础防御力"),
    "ja": ("光円錐", "最大レベル 80", "重畳", "昇格素材", "レベル 1 - 80", "基礎HP", "基礎攻撃力", "基礎防御力"),
    "ko": ("광추", "최대 레벨 80", "중첩", "승급 재료", "레벨 1 - 80", "기초 HP", "기초 공격력", "기초 방어력"),
}


def _font(size: int, locale: str = "en", bold: bool = False):
    if locale != "en":
        try:
            return localized_font(size, bold=bold, locale=locale)
        except OSError:
            pass
    return HSRFonts.get_font(size, "bold" if bold else "regular")


def _clean(text: str | None, locale: str = "en") -> str:
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]*>", "", text).replace("\\n", "\n")
    return unescape(clean_localized(text, locale) or "").strip()


def _number(value: float | int, percent: bool = False) -> str:
    number = Decimal(str(value)) * (100 if percent else 1)
    # Avoid binary float artifacts while retaining fractional superimposition values.
    text = format(number.quantize(Decimal("0.000001")), "f").rstrip("0").rstrip(".")
    return text or "0"


def refinement_description(detail: LightConeDetail, locale: str = "en") -> str:
    """Expand changing values in S1/S2/S3/S4/S5 order; collapse constants."""
    refinement = detail.refinements
    if refinement is None:
        return ""
    text = _clean(refinement.desc, locale)
    levels = refinement.levels

    def substitute(match: re.Match) -> str:
        index = int(match.group(1)) - 1
        if any(rank not in levels or index >= len(levels[rank]) for rank in range(1, 6)):
            raise ValueError(f"Missing S1-S5 parameter #{index + 1} for Light Cone {detail.id}")
        percent = bool(match.group(2))
        values = [_number(levels[rank][index], percent) for rank in range(1, 6)]
        display = values[0] if len(set(values)) == 1 else "/".join(values)
        return display + ("%" if percent else "")

    return PARAM_RE.sub(substitute, text)


def level_80_stats(detail: LightConeDetail) -> dict[str, int]:
    rows = [row for row in detail.stats if (row.max_level or 0) >= 80]
    if not rows:
        raise ValueError(f"Level-80 stats are missing for Light Cone {detail.id}")
    row = max(rows, key=lambda entry: entry.promotion or 0)
    result = {}
    for label, base, growth in (
        ("hp", row.base_hp, row.base_hp_add),
        ("atk", row.base_attack, row.base_attack_add),
        ("def", row.base_defence, row.base_defence_add),
    ):
        if base is None or growth is None:
            raise ValueError(f"Missing level-80 {label} for Light Cone {detail.id}")
        result[label] = math.floor(base + growth * 79 + 0.5)
    return result


def ascension_costs(detail: LightConeDetail) -> dict[int, int]:
    """Sum promotion costs through the final ascension, without EXP costs."""
    costs: dict[int, int] = {}
    for row in detail.stats:
        if row.promotion is not None and row.promotion > 6:
            continue
        for cost in row.promotion_cost_list:
            costs[cost.item_id] = costs.get(cost.item_id, 0) + cost.item_num
    return dict(sorted(costs.items()))


@dataclass
class LightConeData:
    identifier: int
    name: str
    version: str
    locale: str
    detail: LightConeDetail
    stars: int
    path: str
    effect_name: str
    description: str
    stats: dict[str, int]
    costs: dict[int, int]
    client: NanokaClient
    items: dict[str, Any] = field(default_factory=dict)
    art: Image.Image | None = None
    path_icon: Image.Image | None = None
    icons: dict[int, Image.Image] = field(default_factory=dict)


class LCInfoCardResult:
    """PIL-compatible Light Cone card with version and cache metadata."""

    def __init__(self, image, data: LightConeData, *, version, cache_path=None):
        self.image = image
        self.light_cone = data.name
        self.identifier = data.identifier
        self.version = version
        self.cache_path = cache_path
        self.description = data.description
        self.stats = dict(data.stats)

    def save(self, *args, **kwargs):
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self.image, name)


async def load_light_cone(
    identifier: int | str, *, version=None, locale="en", cache_dir=None, proxy=None,
) -> LightConeData:
    locale = normalize_locale(locale)
    client = NanokaClient(version=version, language=locale, cache_dir=cache_dir,
                          proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        cone = await client.get_lightcone(identifier)
        if cone is None or cone.detail is None:
            raise NanokaNotFoundError("lightcone", identifier)
        detail = cone.detail
        return LightConeData(
            identifier=cone.summary.id,
            name=_clean(cone.summary.display_name(locale) or detail.name, locale),
            version=client.version, locale=locale, detail=detail,
            stars=cone.summary.stars or detail.stars or 5,
            path=detail.path_codename or cone.summary.path_codename or "",
            effect_name=_clean(detail.refinements.name if detail.refinements else "", locale),
            description=refinement_description(detail, locale),
            stats=level_80_stats(detail), costs=ascension_costs(detail), client=client,
        )
    except BaseException:
        await client.close()
        raise


def _open(path: Path | None) -> Image.Image | None:
    if path is None:
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGBA")
    except (OSError, ValueError):
        return None


async def _load_assets(data: LightConeData):
    data.art = _open(await data.client.fetch_asset(f"lightconemediumicon/{data.identifier}.webp"))
    data.path_icon = _open(await data.client.fetch_asset(f"pathicon/{data.path}.webp")) if data.path else None
    data.items = await data.client.cache.load_json("item.json") or {}
    for item_id in data.costs:
        icon = _open(await data.client.fetch_asset(f"itemfigures/{item_id}.webp"))
        if icon is not None:
            data.icons[item_id] = icon


@dataclass(frozen=True)
class Run:
    text: str
    color: tuple = TEXT
    bold: bool = False
    strike: bool = False


def _rich(text: str, change: str = "") -> list[Run]:
    result = []
    last = 0
    base = REMOVED if change == "removed" else GREEN if change == "added" else TEXT
    for match in RICH_RE.finditer(text):
        if match.start() > last:
            result.append(Run(text[last:match.start()], base, strike=change == "removed"))
        token = match.group()
        color = base if change else GOLD if token[0].isdigit() else CYAN
        result.append(Run(token, color, True, change == "removed"))
        last = match.end()
    if last < len(text):
        result.append(Run(text[last:], base, strike=change == "removed"))
    return result


def effect_runs(data: LightConeData, before: LightConeData | None = None) -> list[Run]:
    if before is None or before.description == data.description:
        return _rich(data.description)
    def tokens(text):
        if data.locale in {"zh", "ja"}:
            return re.findall(r"\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*%?|.", text, re.S)
        return re.findall(r"\S+\s*|\s+", text)
    left, right = tokens(before.description), tokens(data.description)
    runs = []
    for kind, a, b, c, d in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if kind == "equal":
            runs.extend(_rich("".join(right[c:d])))
        else:
            if a < b:
                runs.extend(_rich("".join(left[a:b]).rstrip(), "removed"))
            if a < b and c < d:
                runs.append(Run(" -> ", MUTED, True))
            if c < d:
                runs.extend(_rich("".join(right[c:d]), "added"))
            elif a < b:
                runs.append(Run(" "))
    return runs


def layout_runs(runs: list[Run], width: int, locale: str, size=BODY_SIZE) -> list[list[Run]]:
    """Measure with the actual regular/bold fonts; keep slash sequences together."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    fonts = {bold: _font(size, locale, bold) for bold in (False, True)}
    lines: list[list[Run]] = [[]]
    used = 0.0
    for run in runs:
        units = re.findall(r"\n|[^\S\n]+|[^\s]+", run.text)
        for unit in units:
            if unit == "\n":
                lines.append([])
                used = 0.0
                continue
            # CJK and exceptionally long sequences can wrap at character boundaries.
            pieces = list(unit) if draw.textlength(unit, fonts[run.bold]) > width else [unit]
            for piece in pieces:
                length = draw.textlength(piece, fonts[run.bold])
                if used and used + length > width:
                    lines.append([])
                    used = 0.0
                if not used and piece.isspace():
                    continue
                lines[-1].append(Run(piece, run.color, run.bold, run.strike))
                used += length
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def _draw_runs(draw, lines, x, y, locale, size=BODY_SIZE, line_h=LINE_H):
    baseline = _font(size, locale).getmetrics()[0]
    for index, line in enumerate(lines):
        cursor = float(x)
        for run in line:
            font = _font(size, locale, run.bold)
            draw.text((cursor, y + index * line_h + baseline), run.text, font=font, fill=run.color, anchor="ls")
            width = draw.textlength(run.text, font)
            if run.strike:
                sy = y + index * line_h + size * 0.52
                draw.line((cursor, sy, cursor + width, sy), fill=run.color, width=2)
            cursor += width


def _panel(draw, box):
    draw.rounded_rectangle(box, radius=18, fill=PANEL, outline=EDGE, width=2)


def _fit(draw, text, font, width):
    if draw.textlength(text, font) <= width:
        return text
    while text and draw.textlength(text + "...", font) > width:
        text = text[:-1]
    return text.rstrip() + "..."


def _paste(canvas, image, box):
    if image is None:
        return
    fitted = ImageOps.contain(image, (box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    x = box[0] + (box[2] - box[0] - fitted.width) // 2
    y = box[1] + (box[3] - box[1] - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))


def render_light_cone(data: LightConeData, before: LightConeData | None = None) -> Image.Image:
    labels = LABELS.get(data.locale, LABELS["en"])
    runs = effect_runs(data, before)
    lines = layout_runs(runs, W - M * 2 - 64, data.locale)
    title_lines = layout_runs([Run(data.name, TEXT, True)], 630, data.locale, size=42)
    path_y = max(218, 116 + len(title_lines) * 48)
    rarity_y = max(293, path_y + 74)
    stats_y = rarity_y + 47
    effect_y = stats_y + 160
    effect_h = 130 + len(lines) * LINE_H
    costs = dict(data.costs)
    if before:
        for item_id in before.costs:
            costs.setdefault(item_id, 0)
    columns = min(7, max(1, len(costs)))
    material_rows = math.ceil(len(costs) / columns)
    material_h = 78 + material_rows * 144
    height = max(MIN_H, effect_y + effect_h + 22 + material_h + 58)
    height = math.ceil(height / 8) * 8
    canvas = Image.new("RGBA", (W, height), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((M, 30), labels[0], font=_font(22, data.locale, True), fill=PURPLE)
    version = f"{before.version} -> {data.version}" if before else data.version
    draw.text((W - M, 30), version, font=_font(22, data.locale, True), fill=MUTED, anchor="rt")
    _panel(draw, (M, 84, 380, stats_y + 134))
    _paste(canvas, data.art, (M + 8, 92, 372, stats_y + 126))
    if data.art is None:
        draw.text((214, 280), labels[0], font=_font(24, data.locale, True), fill=MUTED, anchor="mm")
    _draw_runs(draw, title_lines, 410, 104, data.locale, size=42, line_h=48)
    path_label = PATH_LABELS.get(data.locale, PATH_LABELS["en"]).get(data.path, data.path.title())
    _paste(canvas, data.path_icon, (410, path_y, 450, path_y + 40))
    draw.text((462, path_y + 7), path_label, font=_font(26, data.locale, True), fill=PURPLE, anchor="lt")
    for index in range(data.stars):
        make_star(canvas, 423 + index * 28, rarity_y, 10, GOLD)
    draw.text((W - M, rarity_y - 11), labels[1], font=_font(21, data.locale, True), fill=CYAN, anchor="rt")
    for index, key in enumerate(("hp", "atk", "def")):
        x = 410 + index * 214
        _panel(draw, (x, stats_y, x + 198, stats_y + 134))
        draw.text((x + 18, stats_y + 17), labels[5 + index], font=_font(20, data.locale), fill=MUTED, anchor="lt")
        draw.text((x + 18, stats_y + 53), f"{data.stats[key]:,}", font=_font(42, data.locale, True), fill=TEXT, anchor="lt")
        if before and before.stats[key] != data.stats[key]:
            old = f"{before.stats[key]:,}"
            old_font = _font(19, data.locale)
            draw.text((x + 18, stats_y + 107), old + " ->", font=old_font, fill=REMOVED, anchor="lt")
            draw.line((x + 18, stats_y + 115, x + 18 + draw.textlength(old, old_font), stats_y + 115), fill=REMOVED, width=2)
    _panel(draw, (M, effect_y, W - M, effect_y + effect_h))
    effect_title = data.effect_name or labels[2]
    title_width = 750 if before and before.description != data.description else 920
    draw.text((M + 32, effect_y + 24), _fit(draw, effect_title, _font(32, data.locale, True), title_width),
              font=_font(32, data.locale, True), fill=TEXT, anchor="lt")
    draw.text((M + 32, effect_y + 73), labels[2] + "  1 / 2 / 3 / 4 / 5",
              font=_font(21, data.locale, True), fill=GOLD, anchor="lt")
    _draw_runs(draw, lines, M + 32, effect_y + 116, data.locale)
    if before and before.description != data.description:
        draw.rounded_rectangle((W - M - 146, effect_y + 19, W - M - 20, effect_y + 53), radius=8, fill=(42, 76, 56))
        draw.text((W - M - 83, effect_y + 36), "CHANGED", font=_font(18, bold=True), fill=GREEN, anchor="mm")
    my = max(effect_y + effect_h + 22, height - material_h - 58)
    _panel(draw, (M, my, W - M, my + material_h))
    draw.text((M + 24, my + 20), labels[3], font=_font(24, data.locale, True), fill=TEXT, anchor="lt")
    draw.text((W - M - 24, my + 25), labels[4], font=_font(19, data.locale), fill=MUTED, anchor="rt")
    tile_w = (W - M * 2 - 40) // columns
    for index, (item_id, amount) in enumerate(costs.items()):
        x = M + 20 + (index % columns) * tile_w
        y = my + 65 + (index // columns) * 144
        draw.rounded_rectangle((x + 4, y, x + tile_w - 4, y + 132), radius=12, fill=(18, 16, 30), outline=EDGE)
        icon = data.icons.get(item_id) or (before.icons.get(item_id) if before else None)
        _paste(canvas, icon, (x + 24, y + 6, x + tile_w - 24, y + 86))
        if icon is None:
            name = material_name(data.items, item_id, data.locale)
            draw.text((x + tile_w // 2, y + 45), _fit(draw, name, _font(15, data.locale), tile_w - 12),
                      font=_font(15, data.locale), fill=MUTED, anchor="mm")
        label = f"{amount:,}"
        if before and before.costs.get(item_id, 0) != amount:
            label = f"{before.costs.get(item_id, 0):,} -> {amount:,}"
        size = 25 if len(label) < 10 else 18
        draw.text((x + tile_w // 2, y + 107), label, font=_font(size, data.locale, True),
                  fill=GOLD if item_id == 2 else TEXT, anchor="mm")
    draw.text((M, height - 30), "HSR  /  NANOKA", font=_font(18, bold=True), fill=MUTED, anchor="lm")
    draw.text((W - M, height - 30), f"ID {data.identifier}  ·  LV. 80", font=_font(18), fill=MUTED, anchor="rm")
    return canvas


async def get_LC_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> LCInfoCardResult:
    """Render a level-80 Light Cone with inline S1-S5 effect values.

    Arguments and single/comparison version semantics match get_character_info.
    """
    from_version, to_version = parse_versions(version)
    before = None
    data = await load_light_cone(identifier, version=from_version, locale=locale,
                                 cache_dir=cache_dir, proxy=proxy)
    try:
        if to_version:
            before = data
            data = await load_light_cone(before.identifier, version=to_version, locale=locale,
                                         cache_dir=cache_dir, proxy=proxy)
        versions = (before.version, data.version) if before else data.version
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        image = None if force_refresh else cache.load(data.name, "lc_info", versions, locale=locale)
        path = None
        if image is None:
            await _load_assets(data)
            if before:
                await _load_assets(before)
            image = await asyncio.to_thread(render_light_cone, data, before)
            if use_rendered_cache:
                path = cache.save(image, data.name, "lc_info", versions, locale=locale)
        else:
            path = cache.path(data.name, "lc_info", versions, locale=locale)
        return LCInfoCardResult(image, data, version=versions, cache_path=path)
    finally:
        await data.client.close()
        if before is not None and before is not data:
            await before.client.close()


__all__ = ["LCInfoCardResult", "get_LC_info"]
