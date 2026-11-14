"""Prydwen tier-list cards, following the site's four-role grid."""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from ...prydwen.tier_list import GameMode, TierCharacter, TierListData, fetch_tier_list
from ...utils.hsrfonts import HSRFonts

W, TIER_W, ROLE_W = 1280, 64, 304
CARD_W, CARD_GAP, PAD = 112, 20, 16
TITLE_H, HEADER_H, GROUP_H, FOOTER_H = 96, 44, 58, 44
BG = (35, 36, 42)
PANELS = ((44, 45, 51), (54, 55, 63))
TEXT = (225, 227, 233)
GREEN, RED = (114, 230, 153), (255, 85, 89)
ROLE_COLORS = {
    "dps": (255, 65, 74),
    "debuffer": (194, 103, 239),
    "support": (255, 203, 30),
    "sustain": (122, 224, 155),
}
TIER_COLORS = {
    "t0": (244, 79, 79), "t05": (238, 99, 101),
    "t1": (255, 168, 97), "t15": (255, 192, 130), "t2": (255, 212, 157),
    "t3": (191, 255, 113), "t4": (161, 248, 162), "t5": (114, 241, 243),
}
GROUP_COLORS = {
    "apex": RED, "meta": (255, 192, 130),
    "niche": (155, 248, 141), "forgotten": (103, 238, 245),
}
_ASSETS = Path(__file__).resolve().parents[2] / "assets"


def _font(size: int, weight: str = "bold"):
    return HSRFonts.get_font(size, weight)


def _fit(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "...", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "..."


def _tag_lines(character: TierCharacter) -> list[list[tuple[str, tuple[int, int, int]]]]:
    """Wrap tags by their measured width, retaining each tag's color."""
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    font = _font(14)
    lines: list[list[tuple[str, tuple[int, int, int]]]] = []
    line: list[tuple[str, tuple[int, int, int]]] = []
    width = 0.0
    for index, tag in enumerate(character.tags):
        color = GREEN if tag.casefold() in {"advance", "buff", "energy", "sp-friendly"} else TEXT
        if tag.casefold() == "sp-unfriendly":
            color = RED
        label = tag.upper() + ("," if index < len(character.tags) - 1 else "")
        # Long SP labels may break at the hyphen, as on Prydwen.
        words = label.replace("-", "- ").split() if draw.textlength(label, font) > CARD_W else [label]
        for word in words:
            word_width = draw.textlength(word, font)
            space = draw.textlength(" ", font) if line else 0
            if line and width + space + word_width > CARD_W:
                lines.append(line)
                line, width, space = [], 0.0, 0
            line.append((word, color))
            width += space + word_width
    if line:
        lines.append(line)
    return lines


def _role_layout(characters: list[TierCharacter]) -> tuple[list[tuple[TierCharacter, int, int]], int]:
    tiles = []
    y = PAD
    for index in range(0, len(characters), 2):
        pair = characters[index:index + 2]
        row_h = CARD_W + max((len(_tag_lines(c)) * 17 + 8 for c in pair), default=0)
        for column, character in enumerate(pair):
            x = (ROLE_W - CARD_W * 2 - CARD_GAP) // 2 + column * (CARD_W + CARD_GAP)
            tiles.append((character, x, y))
        y += row_h + 14
    return tiles, max(CARD_W + PAD * 2, y - 14 + PAD)


class TierListRenderer:
    """Render parsed tiers; each portrait URL is downloaded once per card.

    Missing or invalid portrait downloads produce a named placeholder. Fetching
    or parsing the tier list itself still raises an error.
    """

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session
        self.proxy = proxy
        self.timeout = timeout
        self._owns_session = session is None

    async def __aenter__(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self._owns_session and self.session is not None:
            await self.session.close()
            self.session = None

    async def _fetch_image(self, url: str) -> Image.Image | None:
        if not url:
            return None
        if self.session is None:
            raise RuntimeError("Use TierListRenderer as an async context manager")
        try:
            async with self.session.get(
                url, proxy=self.proxy, timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                response.raise_for_status()
                content = await response.read()
            with Image.open(BytesIO(content)) as image:
                return image.convert("RGBA")
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, UnidentifiedImageError):
            return None

    async def render_tier_list(self, data: TierListData) -> Image.Image:
        if len(data.roles) != 4:
            raise ValueError("The HSR tier-list renderer requires four role headers")
        if not data.tiers:
            raise ValueError("The tier list contains no tiers")
        urls = dict.fromkeys(
            character.icon_url
            for tier in data.tiers for role in tier.roles for character in role.characters
            if character.icon_url
        )
        semaphore = asyncio.Semaphore(8)

        async def load(url: str):
            async with semaphore:
                return await self._fetch_image(url)

        images = dict(zip(urls, await asyncio.gather(*(load(url) for url in urls))))
        return await asyncio.to_thread(self._render, data, images)

    def _render(self, data: TierListData, images: dict[str, Image.Image | None]) -> Image.Image:
        rows = []
        for group in data.groups:
            for tier in group.tiers:
                roles = {role.key: role.characters for role in tier.roles}
                layouts = [_role_layout(roles.get(header.key, [])) for header in data.roles]
                rows.append((tier, layouts, max(height for _, height in layouts)))
        height = TITLE_H + HEADER_H + len(data.groups) * GROUP_H + FOOTER_H
        height += sum(row_h + 10 for _, _, row_h in rows)
        image = Image.new("RGB", (W, height), BG)
        draw = ImageDraw.Draw(image)
        draw.text((24, 18), "HONKAI: STAR RAIL", font=_font(28), fill=TEXT)
        draw.text((24, 56), f"PRYDWEN TIER LIST  /  {data.mode.upper()}", font=_font(16), fill=(180, 183, 195))
        if data.updated:
            draw.text((W - 24, 32), f"Updated {data.updated}", anchor="rm", font=_font(16), fill=TEXT)
        for column, header in enumerate(data.roles):
            x = TIER_W + column * ROLE_W
            draw.rectangle((x, TITLE_H, x + ROLE_W - 1, TITLE_H + HEADER_H - 1), fill=PANELS[column % 2])
            draw.text((x + ROLE_W // 2, TITLE_H + HEADER_H // 2), header.name.upper(),
                      anchor="mm", font=_font(18), fill=ROLE_COLORS.get(header.key, TEXT))
        elements = {}
        for path in (_ASSETS / "elements").glob("*.png"):
            with Image.open(path) as element:
                elements[path.stem] = element.convert("RGBA").resize((18, 18), Image.Resampling.LANCZOS)
        y = TITLE_H + HEADER_H
        row_index = 0
        for group in data.groups:
            color = GROUP_COLORS.get(group.key, TEXT)
            label = group.name.upper()
            label_w = draw.textlength(label, _font(24))
            draw.line((0, y + GROUP_H // 2, (W - label_w) // 2 - 22, y + GROUP_H // 2), fill=color, width=2)
            draw.line(((W + label_w) // 2 + 22, y + GROUP_H // 2, W, y + GROUP_H // 2), fill=color, width=2)
            draw.text((W // 2, y + GROUP_H // 2), label, anchor="mm", font=_font(24), fill=color)
            y += GROUP_H
            for _ in group.tiers:
                tier, layouts, row_h = rows[row_index]
                row_index += 1
                color = TIER_COLORS.get(tier.key, GROUP_COLORS.get(group.key, TEXT))
                draw.rectangle((0, y, TIER_W - 1, y + row_h - 1), fill=color)
                draw.text((TIER_W // 2, y + row_h // 2), tier.name, anchor="mm", font=_font(24), fill=(20, 21, 26))
                for column, (tiles, _) in enumerate(layouts):
                    x = TIER_W + column * ROLE_W
                    draw.rectangle((x, y, x + ROLE_W - 1, y + row_h - 1), fill=PANELS[column % 2])
                    for character, dx, dy in tiles:
                        self._draw_character(image, character, x + dx, y + dy, images.get(character.icon_url), elements)
                y += row_h + 10
        draw.text((24, height - FOOTER_H // 2), "Source: " + data.source,
                  anchor="lm", font=_font(14, "regular"), fill=(164, 168, 182))
        return image

    @staticmethod
    def _draw_character(image, character, x, y, portrait, elements):
        draw = ImageDraw.Draw(image)
        top, bottom = ((83, 61, 72), (198, 164, 100)) if character.rarity == 5 else ((53, 45, 80), (133, 88, 193))
        for dy in range(CARD_W):
            t = dy / (CARD_W - 1)
            color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
            draw.line((x, y + dy, x + CARD_W - 1, y + dy), fill=color)
        if portrait is not None:
            avatar = ImageOps.fit(portrait, (CARD_W, CARD_W), method=Image.Resampling.LANCZOS)
            image.paste(avatar, (x, y), avatar)
        else:
            initials = "".join(word[0] for word in character.name.split()[:2])
            draw.text((x + CARD_W // 2, y + 40), initials, anchor="mm", font=_font(30), fill=TEXT)
            draw.text((x + CARD_W // 2, y + 75), _fit(draw, character.name, _font(13), CARD_W - 8),
                      anchor="mm", font=_font(13), fill=TEXT)
        element = elements.get(character.element.casefold())
        if element is not None:
            draw.rectangle((x, y, x + 21, y + 21), fill=BG)
            image.paste(element, (x + 2, y + 2), element)
        if character.eidolon:
            font = _font(13)
            width = max(25, int(draw.textlength(character.eidolon, font)) + 10)
            draw.rectangle((x + CARD_W - width, y + CARD_W - 25, x + CARD_W - 1, y + CARD_W - 1), fill=bottom)
            draw.text((x + CARD_W - width // 2, y + CARD_W - 12), character.eidolon, anchor="mm",
                      font=font, fill=(20, 21, 26) if character.rarity == 5 else (255, 255, 255))
        for index, mark in enumerate(character.marks):
            bx, by = x + CARD_W - 26, y + index * 26
            if mark == "new":
                draw.rectangle((bx - 13, by, bx + 25, by + 24), fill=(244, 49, 70))
                draw.text((bx + 6, by + 12), "NEW", font=_font(12), anchor="mm", fill=(255, 255, 255))
            elif mark in {"up", "down"}:
                color = (125, 221, 164) if mark == "up" else RED
                ink = (21, 52, 39) if mark == "up" else (255, 255, 255)
                draw.rectangle((bx, by, bx + 25, by + 24), fill=color)
                cx, cy = bx + 13, by + 12
                tip = cy - 6 if mark == "up" else cy + 6
                tail = cy + 6 if mark == "up" else cy - 6
                draw.line((cx, tail, cx, tip), fill=ink, width=2)
                draw.line((cx - 5, cy, cx, tip, cx + 5, cy), fill=ink, width=2)
            elif mark == "watchlist":
                draw.rectangle((bx, by, bx + 25, by + 24), fill=(55, 121, 226))
                draw.ellipse((bx + 4, by + 7, bx + 21, by + 17), fill="white")
                draw.ellipse((bx + 10, by + 9, bx + 15, by + 15), fill=(55, 121, 226))
        font = _font(14)
        for line_index, line in enumerate(_tag_lines(character)):
            text = " ".join(word for word, _ in line)
            tx = x + (CARD_W - draw.textlength(text, font)) / 2
            for index, (word, color) in enumerate(line):
                label = (" " if index else "") + word
                draw.text((tx, y + CARD_W + 8 + line_index * 17), label, font=font, fill=color)
                tx += draw.textlength(label, font)


async def tier_list(
    game_mode: GameMode = "MOC",
    *,
    raw: bool = False,
    timeout: float = 30.0,
    proxy: str | None = None,
) -> Image.Image | tuple[Image.Image, TierListData]:
    """Render Prydwen's MOC, PF, or AS list; ``raw=True`` also returns its data.

    This standalone entry point requires no player UID or HoYoLAB cookies.
    """
    data = await fetch_tier_list(game_mode=game_mode, timeout=timeout, proxy=proxy)
    async with TierListRenderer(proxy=proxy, timeout=timeout) as renderer:
        image = await renderer.render_tier_list(data)
    return (image, data) if raw else image


__all__ = ["TierListRenderer", "tier_list"]
