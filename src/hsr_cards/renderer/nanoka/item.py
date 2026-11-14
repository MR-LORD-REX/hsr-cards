"""Nanoka item cards with acquisition sources and inline version comparisons."""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from ...nanoka import NanokaClient
from ...nanoka.exceptions import NanokaNotFoundError
from ...nanoka.models import ItemSummary
from .character_info import make_star
from .data import RenderedCardCache, normalize_locale, parse_versions
from .light_cone import (
    BG, GOLD, GREEN, MUTED, PURPLE, REMOVED, TEXT, Run,
    _clean, _draw_runs, _font, _open, _panel, _paste, _rich, layout_runs,
)
from .relic import comparison_runs

W, MIN_H, M = 1080, 1350, 48
LABELS = {
    "en": ("ITEM", "DESCRIPTION", "SOURCES", "No description available.", "No sources listed.", "Rarity unavailable"),
    "zh": ("物品", "描述", "获取途径", "暂无描述。", "暂无获取途径。", "稀有度未知"),
    "ja": ("アイテム", "説明", "入手方法", "説明はありません。", "入手方法は記載されていません。", "レアリティ不明"),
    "ko": ("아이템", "설명", "획득 경로", "설명이 없습니다.", "등록된 획득 경로가 없습니다.", "희귀도 정보 없음"),
}
LOCALES = ("en", "zh", "ja", "ko")
PURPOSES = {
    1: ("Character EXP Material", "角色经验材料", "キャラクター経験値素材", "캐릭터 경험치 재료"),
    2: ("Character Ascension Material", "角色晋阶材料", "キャラクター昇格素材", "캐릭터 승급 재료"),
    3: ("Trace Material", "行迹材料", "軌跡素材", "행적 재료"),
    4: ("Advanced Trace Material", "高阶行迹材料", "上級軌跡素材", "고급 행적 재료"),
    5: ("Light Cone EXP Material", "光锥经验材料", "光円錐経験値素材", "광추 경험치 재료"),
    6: ("Relic EXP Material", "遗器经验材料", "遺物経験値素材", "유물 경험치 재료"),
    7: ("Character and Light Cone Enhancement Material", "角色与光锥强化材料", "キャラクター・光円錐強化素材", "캐릭터 및 광추 강화 재료"),
    8: ("Regular Warp Ticket", "常驻跃迁票券", "通常跳躍チケット", "일반 워프 티켓"),
    9: ("Special Warp Ticket", "活动跃迁票券", "限定跳躍チケット", "이벤트 워프 티켓"),
    10: ("Special Item", "特殊物品", "特殊アイテム", "특수 아이템"),
    11: ("Currency", "货币", "通貨", "화폐"),
    12: ("Premium Currency", "星际货币", "星間通貨", "성간 화폐"),
    13: ("World Currency", "世界货币", "地域通貨", "지역 화폐"),
    14: ("Gift and Special Item", "礼品与特殊物品", "ギフト・特殊アイテム", "선물 및 특수 아이템"),
    16: ("Mission Item", "任务物品", "クエストアイテム", "임무 아이템"),
    17: ("Synthesis Material", "合成材料", "合成素材", "합성 재료"),
    19: ("Recipe", "配方", "レシピ", "레시피"),
    21: ("Readable", "阅读物", "読み物", "읽을거리"),
}
TYPE_NAMES = {
    "Material": ("Material", "材料", "素材", "재료"),
    "Mission": ("Mission Item", "任务物品", "クエストアイテム", "임무 아이템"),
    "Usable": ("Consumable", "消耗品", "消耗品", "소모품"),
    "Virtual": ("Currency", "货币", "通貨", "화폐"),
    "EquipmentExp": PURPOSES[5], "AvatarExp": PURPOSES[1], "AvatarRank": PURPOSES[2],
    "TracePath": PURPOSES[3], "WeeklyMonsterDrop": PURPOSES[4],
    "RelicExp": PURPOSES[6], "CommonMonsterDrop": PURPOSES[7],
    "ComposeMaterial": PURPOSES[17], "Formula": PURPOSES[19], "Book": PURPOSES[21],
}


def _localized(values, locale):
    return values[LOCALES.index(locale) if locale in LOCALES else 0]


def _type_name(value: str, locale: str) -> str:
    if value in TYPE_NAMES:
        return _localized(TYPE_NAMES[value], locale)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value).replace("Exp", "EXP")


def item_asset(item: ItemSummary) -> str:
    """Use the published artwork stem; it can differ from the inventory ID."""
    icon = item.item_figure_icon_path or item.item_icon_path or item.item_currency_icon_path
    stem = Path(icon.replace("\\", "/")).stem if icon else str(item.id)
    return f"itemfigures/{stem}.webp"


@dataclass
class ItemData:
    identifier: int
    name: str
    version: str
    locale: str
    summary: ItemSummary
    description: str
    background: str
    purpose: str
    main_type: str
    sub_type: str
    sources: dict[int, str]
    client: NanokaClient
    art: Image.Image | None = None


class ItemInfoCardResult:
    """PIL-compatible item card with localized descriptions and sources."""

    def __init__(self, image, data: ItemData, *, version, cache_path=None):
        self.image = image
        self.item = data.name
        self.identifier = data.identifier
        self.version = version
        self.cache_path = cache_path
        self.description = data.description
        self.background = data.background
        self.purpose = data.purpose
        self.rarity = data.summary.stars
        self.main_type = data.main_type
        self.sub_type = data.sub_type
        self.sources = list(data.sources.values())

    def save(self, *args, **kwargs):
        return self.image.save(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.image, name)


async def load_item(
    identifier: int | str, *, version=None, locale="en", cache_dir=None, proxy=None,
) -> ItemData:
    locale = normalize_locale(locale)
    client = NanokaClient(version=version, language=locale, cache_dir=cache_dir,
                          proxy=proxy, include_assets=False)
    try:
        await client.initialize()
        item = await client.get_item(identifier)
        if item is None:
            raise NanokaNotFoundError("item", identifier)
        background = _clean(item.item_bg_desc, locale)
        sources = {}
        for index, source in enumerate(item.item_comefrom):
            text = _clean(source.desc, locale)
            if text:
                sources[source.id if source.id is not None else -(index + 1)] = text
        purpose = (_localized(PURPOSES[item.purpose_type], locale) if item.purpose_type in PURPOSES
                   else _type_name(item.item_sub_type or item.item_main_type or "", locale))
        return ItemData(
            identifier=item.id, name=_clean(item.name, locale) or str(item.id),
            version=client.version, locale=locale, summary=item,
            description=_clean(item.item_desc, locale) or background, background=background,
            purpose=purpose, main_type=item.item_main_type or "", sub_type=item.item_sub_type or "",
            sources=sources, client=client,
        )
    except BaseException:
        await client.close()
        raise


async def _load_assets(data: ItemData):
    relative = item_asset(data.summary)
    data.art = _open(await data.client.fetch_asset(relative))
    icon = data.summary.item_icon_path
    if data.art is None and icon:
        fallback = f"itemfigures/{Path(icon.replace(chr(92), '/')).stem}.webp"
        if fallback != relative:
            data.art = _open(await data.client.fetch_asset(fallback))


def source_rows(data: ItemData, before: ItemData | None = None):
    """Match sources by stable IDs, retaining removed acquisition methods."""
    old = before.sources if before else {}
    keys = list(data.sources) + [key for key in old if key not in data.sources]
    rows = []
    for key in keys:
        text, previous = data.sources.get(key, ""), old.get(key)
        if key not in data.sources:
            status, runs = "REMOVED", _rich(previous or "", "removed")
        elif before is not None and key not in old:
            status, runs = "ADDED", _rich(text, "added")
        else:
            status = "CHANGED" if previous is not None and previous != text else ""
            runs = comparison_runs(text, previous, data.locale)
        rows.append((key, status, runs))
    return rows


def _badge(draw, status, right, y):
    if status:
        draw.text((right, y), status, font=_font(18, bold=True),
                  fill=REMOVED if status == "REMOVED" else GREEN, anchor="rt")


def _categories(data: ItemData) -> str:
    names = [_type_name(value, data.locale) for value in (data.main_type, data.sub_type) if value]
    return " / ".join(dict.fromkeys(names))


def render_item(data: ItemData, before: ItemData | None = None) -> Image.Image:
    labels = LABELS.get(data.locale, LABELS["en"])
    text_x, text_w = 452, W - M - 452
    title = [replace(run, bold=True) for run in comparison_runs(data.name, before.name if before else None, data.locale)]
    title_lines = layout_runs(title, text_w, data.locale, size=42)
    purpose_y = 104 + len(title_lines) * 50 + 24
    purpose_lines = layout_runs(comparison_runs(data.purpose, before.purpose if before else None, data.locale),
                                text_w, data.locale, size=26)
    category_y = purpose_y + len(purpose_lines) * 36 + 22
    category_lines = layout_runs(comparison_runs(_categories(data), _categories(before) if before else None, data.locale),
                                 text_w, data.locale, size=23)
    rarity_y = category_y + len(category_lines) * 32 + 28
    header_bottom = max(484, rarity_y + 48)
    desc_y = header_bottom + 28
    desc_runs = comparison_runs(data.description, before.description if before else None, data.locale)
    desc_lines = layout_runs(desc_runs or [Run(labels[3], MUTED)], W - M * 2 - 64, data.locale)
    desc_h = 86 + len(desc_lines) * 44
    sources_y = desc_y + desc_h + 24
    sources = [(status, layout_runs(runs, W - M * 2 - 96 - (112 if status else 0), data.locale, size=30))
               for _, status, runs in source_rows(data, before)]
    row_heights = [len(lines) * 42 + 28 for _, lines in sources]
    sources_h = 84 + sum(row_heights) if sources else 142
    height = math.ceil(max(MIN_H, sources_y + sources_h + 72) / 2) * 2
    canvas = Image.new("RGBA", (W, height), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((M, 30), labels[0], font=_font(22, data.locale, True), fill=PURPLE)
    version = f"{before.version} -> {data.version}" if before else data.version
    draw.text((W - M, 30), version, font=_font(22, data.locale, True), fill=MUTED, anchor="rt")
    _panel(draw, (M, 84, 416, header_bottom))
    _paste(canvas, data.art if data.art is not None else before.art if before else None,
           (M + 16, 100, 400, header_bottom - 16))
    if data.art is None and (before is None or before.art is None):
        draw.text((232, (84 + header_bottom) // 2), labels[0], font=_font(26, data.locale, True), fill=MUTED, anchor="mm")
    _draw_runs(draw, title_lines, text_x, 104, data.locale, size=42, line_h=50)
    _draw_runs(draw, purpose_lines, text_x, purpose_y, data.locale, size=26, line_h=36)
    _draw_runs(draw, category_lines, text_x, category_y, data.locale, size=23, line_h=32)
    stars = data.summary.stars
    if before and before.summary.stars != stars:
        runs = comparison_runs(f"{stars or '?'}★", f"{before.summary.stars or '?'}★", data.locale)
        _draw_runs(draw, layout_runs(runs, text_w, data.locale, size=30), text_x, rarity_y - 4, data.locale, size=30)
    elif stars:
        for index in range(stars):
            make_star(canvas, text_x + 12 + index * 32, rarity_y + 12, 11, GOLD)
    else:
        draw.text((text_x, rarity_y), labels[5], font=_font(23, data.locale), fill=MUTED, anchor="lt")
    _panel(draw, (M, desc_y, W - M, desc_y + desc_h))
    draw.text((M + 32, desc_y + 22), labels[1], font=_font(25, data.locale, True), fill=PURPLE, anchor="lt")
    _badge(draw, "CHANGED" if before and before.description != data.description else "", W - M - 24, desc_y + 26)
    _draw_runs(draw, desc_lines, M + 32, desc_y + 68, data.locale)
    _panel(draw, (M, sources_y, W - M, sources_y + sources_h))
    draw.text((M + 32, sources_y + 22), labels[2], font=_font(25, data.locale, True), fill=PURPLE, anchor="lt")
    y = sources_y + 72
    if not sources:
        draw.text((M + 32, y), labels[4], font=_font(30, data.locale), fill=MUTED, anchor="lt")
    for index, ((status, lines), row_h) in enumerate(zip(sources, row_heights)):
        draw.ellipse((M + 32, y + 15, M + 39, y + 22), fill=REMOVED if status == "REMOVED" else PURPLE)
        _draw_runs(draw, lines, M + 56, y, data.locale, size=30, line_h=42)
        _badge(draw, status, W - M - 24, y + 8)
        if index < len(sources) - 1:
            draw.line((M + 32, y + row_h - 10, W - M - 32, y + row_h - 10), fill=(67, 54, 91), width=1)
        y += row_h
    draw.text((M, height - 30), "HSR  /  NANOKA", font=_font(18, bold=True), fill=MUTED, anchor="lm")
    draw.text((W - M, height - 30), f"ITEM ID {data.identifier}", font=_font(18), fill=MUTED, anchor="rm")
    return canvas


async def get_item_info(
    identifier: int | str,
    version: str | Sequence[str] | None = None,
    *,
    locale: str = "en",
    cache_dir: str | Path | None = None,
    proxy: str | None = None,
    rendered_cache_dir: str | Path | None = None,
    use_rendered_cache: bool = True,
    force_refresh: bool = False,
) -> ItemInfoCardResult:
    """Render an inventory item, using the get_character_info arguments."""
    from_version, to_version = parse_versions(version)
    before = None
    data = await load_item(identifier, version=from_version, locale=locale, cache_dir=cache_dir, proxy=proxy)
    try:
        if to_version:
            before = data
            data = await load_item(before.identifier, version=to_version, locale=locale, cache_dir=cache_dir, proxy=proxy)
        versions = (before.version, data.version) if before else data.version
        cache = RenderedCardCache(rendered_cache_dir, enabled=use_rendered_cache)
        # Different inventory items can share a name, including mission and reward items.
        cache_name = f"{data.name}_{data.identifier}"
        image = None if force_refresh else cache.load(cache_name, "item_info", versions, locale=locale)
        path = None
        if image is None:
            await _load_assets(data)
            if before:
                await _load_assets(before)
            image = await asyncio.to_thread(render_item, data, before)
            if use_rendered_cache:
                path = cache.save(image, cache_name, "item_info", versions, locale=locale)
        else:
            path = cache.path(cache_name, "item_info", versions, locale=locale)
        return ItemInfoCardResult(image, data, version=versions, cache_path=path)
    finally:
        await data.client.close()
        if before is not None and before is not data:
            await before.client.close()


__all__ = ["ItemInfoCardResult", "get_item_info"]
