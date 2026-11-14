"""Nanoka relic-set cards, including planar sets and version comparisons."""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import RelicPart, RelicSetDetail, RelicSetEffectDetail
from .data import RenderedCardCache, normalize_locale, parse_versions
from .light_cone import (
    BG, CYAN, GOLD, GREEN, MUTED, PURPLE, REMOVED, TEXT, PARAM_RE, Run,
    _clean, _draw_runs, _font, _number, _open, _panel, _paste, _rich, layout_runs,
)

W, M, GAP = 1080, 48, 16
SLOT_ORDER = {slot: i for i, slot in enumerate(("head", "hands", "body", "feet", "planar_sphere", "link_rope"))}
LABELS = {
    "en": ("RELIC SET", "CAVERN RELICS", "PLANAR ORNAMENTS", "PARTS", "SET EFFECTS", "PIECE SET"),
    "zh": ("遗器套装", "隧洞遗器", "位面饰品", "部件", "套装效果", "件套"),
    "ja": ("遺物セット", "トンネル遺物", "次元界オーナメント", "部位", "セット効果", "セット"),
    "ko": ("유물 세트", "터널 유물", "차원 장신구", "부위", "세트 효과", "세트"),
}
SLOT_LABELS = {
    "en": ("HEAD", "HANDS", "BODY", "FEET", "PLANAR SPHERE", "LINK ROPE"),
    "zh": ("头部", "手部", "躯干", "脚部", "位面球", "连结绳"),
    "ja": ("頭部", "手部", "胴体", "脚部", "次元界オーブ", "連結縄"),
    "ko": ("머리", "핸드", "바디", "신발", "차원 구체", "연결 매듭"),
}


def effect_description(effect: RelicSetEffectDetail, locale="en") -> str:
    text = _clean(effect.desc, locale)
    def substitute(match):
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(effect.param_list):
            raise ValueError(f"Missing parameter #{index + 1} for {effect.pieces}-piece relic effect")
        percent = bool(match.group(2))
        return _number(effect.param_list[index], percent) + ("%" if percent else "")
    return PARAM_RE.sub(substitute, text)


def _part_key(part: RelicPart) -> str:
    return part.slot or str(part.id)


def part_asset(identifier: int, part: RelicPart) -> str:
    if part.icon:
        stem = Path(part.icon.replace("\\", "/")).stem
    elif part.slot:
        stem = f"IconRelic_{identifier}_{part.id % 10}"
    else:
        return ""
    return f"relicfigures/{stem}.webp"


@dataclass
class RelicData:
    identifier: int
    name: str
    version: str
    locale: str
    detail: RelicSetDetail
    effects: dict[int, str]
    parts: list[RelicPart]
    set_type: str
    icon_path: str
    client: NanokaClient
    icon: Image.Image | None = None
    icons: dict[str, Image.Image] = field(default_factory=dict)


class RelicInfoCardResult:
    """PIL-compatible relic card and its localized set/piece metadata."""

    def __init__(self, image, data: RelicData, *, version, cache_path=None):
        self.image = image
        self.relic_set = data.name
        self.identifier = data.identifier
        self.version = version
        self.cache_path = cache_path
        self.set_type = data.set_type
        self.effects = dict(data.effects)
        self.parts = list(data.parts)

    def save(self, *args, **kwargs):
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.image, name)


async def load_relic(
    identifier: int | str, *, version=None, locale="en", cache_dir=None, proxy=None,
) -> RelicData:
    locale = normalize_locale(locale)
    client = NanokaClient(version=version, language=locale, cache_dir=cache_dir,
                          proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        relic = await client.get_relic(identifier)
        if relic is None or relic.detail is None:
            raise NanokaNotFoundError("relicset", identifier)
        detail = relic.detail
        parts = sorted(detail.piece_list, key=lambda part: (SLOT_ORDER.get(part.slot, 99), part.id or 0))
        if not parts or not detail.effects:
            raise ValueError(f"Incomplete relic set {relic.summary.id}: parts or effects are missing")
        icon = detail.icon or relic.summary.icon or ""
        icon_path = f"itemfigures/{Path(icon.replace(chr(92), '/')).stem}.webp" if icon else ""
        return RelicData(
            identifier=relic.summary.id,
            name=_clean(relic.summary.display_name(locale) or detail.name, locale),
            version=client.version, locale=locale, detail=detail,
            effects={effect.pieces: effect_description(effect, locale) for effect in detail.effects},
            parts=parts,
            set_type="planar" if all(part.slot in {"planar_sphere", "link_rope"} for part in parts) else "cavern",
            icon_path=icon_path, client=client,
        )
    except BaseException:
        await client.close()
        raise


async def _load_assets(data: RelicData):
    relatives = {"set": data.icon_path}
    relatives.update({_part_key(part): part_asset(data.identifier, part) for part in data.parts})
    async def load(key, relative):
        return key, _open(await data.client.fetch_asset(relative)) if relative else None
    assets = dict(await asyncio.gather(*(load(key, relative) for key, relative in relatives.items())))
    data.icon = assets.pop("set")
    data.icons = {key: image for key, image in assets.items() if image is not None}
    if data.icon is None:
        data.icon = next(iter(data.icons.values()), None)


def comparison_runs(text: str, previous: str | None, locale: str) -> list[Run]:
    if previous is None or previous == text:
        return _rich(text)
    def tokenize(value):
        if locale in {"zh", "ja"}:
            return re.findall(r"\d+(?:\.\d+)?%?|.", value, re.S)
        return re.findall(r"\S+\s*|\s+", value)
    left, right = tokenize(previous), tokenize(text)
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


def effect_rows(data: RelicData, before: RelicData | None = None):
    """Keep removed bonuses visible, alongside added or changed bonuses."""
    old = before.effects if before else {}
    result = []
    for count in sorted(data.effects.keys() | old.keys()):
        text = data.effects.get(count, "")
        previous = old.get(count)
        if count not in data.effects:
            status, runs = "REMOVED", _rich(previous or "", "removed")
        elif before is not None and count not in old:
            status, runs = "ADDED", _rich(text, "added")
        else:
            status = "CHANGED" if previous is not None and text != previous else ""
            runs = comparison_runs(text, previous, data.locale)
        result.append((count, status, runs))
    return result


def part_rows(data: RelicData, before: RelicData | None = None):
    current = {_part_key(part): part for part in data.parts}
    old = {_part_key(part): part for part in before.parts} if before else {}
    keys = sorted(current.keys() | old.keys(), key=lambda key: (SLOT_ORDER.get(key, 99), key))
    rows = []
    for key in keys:
        part = current.get(key) or old[key]
        name = _clean(part.name, data.locale) or str(part.id)
        previous = _clean(old[key].name, data.locale) if key in old else None
        if key not in current:
            status, runs = "REMOVED", _rich(name, "removed")
        elif before is not None and key not in old:
            status, runs = "ADDED", _rich(name, "added")
        else:
            status = "CHANGED" if previous is not None and name != previous else ""
            runs = comparison_runs(name, previous, data.locale)
        icon = data.icons.get(key)
        if icon is None and before:
            icon = before.icons.get(key)
        rows.append((part, status, runs, icon))
    return rows


def _badge(draw, status, right, y):
    if not status:
        return
    color = REMOVED if status == "REMOVED" else GREEN
    draw.text((right, y), status, font=_font(18, bold=True), fill=color, anchor="rt")


def render_relic(data: RelicData, before: RelicData | None = None) -> Image.Image:
    labels = LABELS.get(data.locale, LABELS["en"])
    title = [replace(run, bold=True) for run in comparison_runs(data.name, before.name if before else None, data.locale)]
    title_lines = layout_runs(title, 780, data.locale, size=42)
    header_bottom = max(254, 138 + len(title_lines) * 50)
    parts_y = header_bottom + 56
    tile_w = (W - M * 2 - GAP) // 2
    pieces = []
    for part, status, runs, icon in part_rows(data, before):
        lines = layout_runs(runs, tile_w - 204, data.locale, size=27)
        pieces.append((part, status, lines, icon))
    row_heights = [max(196, max(len(piece[2]) * 35 + 74 + (32 if piece[1] else 0) for piece in pieces[i:i + 2]))
                   for i in range(0, len(pieces), 2)]
    effects_y = parts_y + sum(row_heights) + GAP * max(0, len(row_heights) - 1) + 42
    bonuses = [(count, status, layout_runs(runs, W - M * 2 - 64, data.locale))
               for count, status, runs in effect_rows(data, before)]
    effect_heights = [84 + len(lines) * 44 for _, _, lines in bonuses]
    natural_height = effects_y + 48 + sum(effect_heights) + GAP * max(0, len(bonuses) - 1) + 64
    height = max(1080 if data.set_type == "planar" else 1350, natural_height)
    height = math.ceil(height / 2) * 2
    canvas = Image.new("RGBA", (W, height), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((M, 30), labels[0], font=_font(22, data.locale, True), fill=PURPLE)
    version = f"{before.version} -> {data.version}" if before else data.version
    draw.text((W - M, 30), version, font=_font(22, data.locale, True), fill=MUTED, anchor="rt")
    _panel(draw, (M, 84, M + 168, 252))
    _paste(canvas, data.icon, (M + 12, 96, M + 156, 240))
    kind = labels[2] if data.set_type == "planar" else labels[1]
    draw.text((244, 94), kind, font=_font(21, data.locale, True), fill=CYAN, anchor="lt")
    _draw_runs(draw, title_lines, 244, 136, data.locale, size=42, line_h=50)
    draw.text((M, header_bottom + 12), labels[3], font=_font(26, data.locale, True), fill=TEXT, anchor="lt")
    y = parts_y
    for row_index, row_h in enumerate(row_heights):
        for column, (part, status, lines, icon) in enumerate(pieces[row_index * 2:row_index * 2 + 2]):
            x = M + column * (tile_w + GAP)
            _panel(draw, (x, y, x + tile_w, y + row_h))
            _paste(canvas, icon, (x + 18, y + 34, x + 158, y + row_h - 24))
            slot = SLOT_LABELS.get(data.locale, SLOT_LABELS["en"])[SLOT_ORDER[part.slot]] if part.slot in SLOT_ORDER else str(part.id)
            draw.text((x + 180, y + 22), slot, font=_font(18, data.locale, True), fill=PURPLE, anchor="lt")
            _draw_runs(draw, lines, x + 180, y + 64, data.locale, size=27, line_h=35)
            _badge(draw, status, x + tile_w - 16, y + row_h - 28)
        y += row_h + GAP
    draw.text((M, effects_y), labels[4], font=_font(26, data.locale, True), fill=TEXT, anchor="lt")
    y = effects_y + 48
    for (count, status, lines), panel_h in zip(bonuses, effect_heights):
        _panel(draw, (M, y, W - M, y + panel_h))
        draw.text((M + 32, y + 22), f"{count}-{labels[5]}" if data.locale == "en" else f"{count}{labels[5]}",
                  font=_font(23, data.locale, True), fill=GOLD, anchor="lt")
        _badge(draw, status, W - M - 24, y + 24)
        _draw_runs(draw, lines, M + 32, y + 66, data.locale)
        y += panel_h + GAP
    draw.text((M, height - 30), "HSR  /  NANOKA", font=_font(18, bold=True), fill=MUTED, anchor="lm")
    draw.text((W - M, height - 30), f"SET ID {data.identifier}", font=_font(18), fill=MUTED, anchor="rm")
    return canvas


async def get_relic_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> RelicInfoCardResult:
    """Render set bonuses and all pieces, using the get_character_info arguments."""
    from_version, to_version = parse_versions(version)
    before = None
    data = await load_relic(identifier, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy)
    try:
        if to_version:
            before = data
            data = await load_relic(before.identifier, version=to_version, locale=locale,
                                    cache_dir=cache_dir, proxy=proxy)
        versions = (before.version, data.version) if before else data.version
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        image = None if force_refresh else cache.load(data.name, "relic_info", versions, locale=locale)
        path = None
        if image is None:
            await _load_assets(data)
            if before:
                await _load_assets(before)
            image = await asyncio.to_thread(render_relic, data, before)
            if use_rendered_cache:
                path = cache.save(image, data.name, "relic_info", versions, locale=locale)
        else:
            path = cache.path(data.name, "relic_info", versions, locale=locale)
        return RelicInfoCardResult(image, data, version=versions, cache_path=path)
    finally:
        await data.client.close()
        if before is not None and before is not data:
            await before.client.close()


__all__ = ["RelicInfoCardResult", "get_relic_info"]
