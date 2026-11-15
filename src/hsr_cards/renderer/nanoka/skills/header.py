"""Draw the character identity, art, stats, bonuses, and page furniture."""
from __future__ import annotations

from PIL import Image
from hsr_cards.renderer.nanoka.character_info import BG
from hsr_cards.renderer.nanoka.character_info import DIM
from hsr_cards.renderer.nanoka.character_info import FIRE
from hsr_cards.renderer.nanoka.character_info import GOLD
from hsr_cards.renderer.nanoka.character_info import LINE
from hsr_cards.renderer.nanoka.character_info import MUTED
from hsr_cards.renderer.nanoka.character_info import PURPLE
from hsr_cards.renderer.nanoka.character_info import TEXT
from hsr_cards.renderer.nanoka.character_info import composite_panel
from hsr_cards.renderer.nanoka.character_info import font
from hsr_cards.renderer.nanoka.character_info import format_bonus
from hsr_cards.renderer.nanoka.character_info import load_webp
from hsr_cards.renderer.nanoka.character_info import make_star
from hsr_cards.renderer.nanoka.character_info import radial
from hsr_cards.renderer.nanoka.character_info import wrap
from hsr_cards.renderer.nanoka.skills.decorations import change_overlay
from hsr_cards.renderer.nanoka.skills.models import SkillData
from hsr_cards.renderer.nanoka.skills.preparation import value_color
from hsr_cards.renderer.nanoka.skills.styles import BODY_SOFT, M, UI_LABELS, WEIGHT_BOLD, WEIGHT_REGULAR, WEIGHT_SEMI
from hsr_cards.renderer.nanoka.skills.text import draw_text_runs
from hsr_cards.renderer.nanoka.skills.typography import font_w, title_font


def ui(data: SkillData, key: str) -> str:
    """Resolve a UI label in data.locale, falling back to English and then the key."""
    labels = UI_LABELS.get(data.locale, UI_LABELS["en"])
    return labels.get(key, UI_LABELS["en"].get(key, key))


def page_background(width: int, height: int) -> Image.Image:
    """Create a width-by-height RGBA canvas with the skills palette and radial glows."""
    canvas = Image.new("RGBA", (width, height), BG)
    canvas.alpha_composite(radial((1500, 1300), (116, 68, 205), 0.30), (-520, -560))
    canvas.alpha_composite(radial((1200, 1200), (217, 87, 57), 0.16), (width - 700, -460))
    return canvas


def wrap_locale(draw, text: str, fnt, width: int, locale: str) -> list[str]:
    """Wrap text to pixel width using word boundaries or Chinese/Japanese glyph boundaries; return display lines."""
    if locale not in ("zh", "ja"):
        return wrap(draw, text, fnt, width)
    lines = []
    for paragraph in text.replace("\\n", "\n").split("\n"):
        line = ""
        for char in paragraph:
            candidate = line + char
            if draw.textlength(candidate, font=fnt) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = char
        if line:
            lines.append(line)
    return lines


def fit(draw, text: str, fnt, width: int) -> str:
    """Return text fitting the measured pixel width, shortening it with an ellipsis when needed."""
    if draw.textlength(text, font=fnt) <= width:
        return text
    suffix = "..."
    while text and draw.textlength(text + suffix, font=fnt) > width:
        text = text[:-1]
    return text.rstrip() + suffix


def version_text(data: SkillData) -> str:
    """Return single/comparison build labels with the uppercase locale suffix."""
    if data.comparison:
        return f"v{data.version_before} \u2192 v{data.version_after}  /  {data.locale.upper()}"
    return f"v{data.version}  /  {data.locale.upper()}"


def version_pill(canvas, draw, data: SkillData, width: int, y: int = 20):
    """Draw a right-aligned single/comparison version pill within the supplied canvas width."""
    text = version_text(data)
    fnt = font(15, bold=True, locale=data.locale)
    text_w = draw.textlength(text, font=fnt)
    x0 = width - M - text_w - 32
    composite_panel(canvas, (x0, y, width - M, y + 40), 20, (19, 13, 33, 246), (255, 255, 255, 66))
    draw.text((x0 + 16, y + 9), text, font=fnt, fill=TEXT)


def trimmed_splash(image: Image.Image) -> Image.Image:
    """Crop low-alpha margins from borrowed RGBA character art, retaining small padding around visible pixels."""
    alpha = image.getchannel("A").point(lambda value: 255 if value > 34 else 0)
    box = alpha.getbbox()
    if box:
        left, top, right, bottom = box
        image = image.crop(
            (
                max(0, left - 24),
                max(0, top - 16),
                min(image.width, right + 24),
                min(image.height, bottom + 16),
            )
        )
    return image


def splash(canvas: Image.Image, data: SkillData, x: int, y: int, target_h: int) -> int:
    """Resize and composite character art/glow at x/y for target_h pixels; return drawn width or zero when absent."""
    if not data.splash:
        return 0
    image = trimmed_splash(data.splash)
    scale = target_h / image.height
    resized = image.resize((round(image.width * scale), target_h), Image.Resampling.LANCZOS)
    canvas.alpha_composite(radial((850, 850), (246, 172, 87, 0.20)), (x - 70, y - 10))
    canvas.alpha_composite(resized, (x, y))
    return resized.width


def art_panel(data: SkillData, width: int, height: int) -> tuple[int, int, int, int]:
    """Left header region that hosts the splash behind the identity text."""
    return 0, 0, 812, height


def scrim(size: tuple[int, int], horizontal: bool) -> Image.Image:
    """Linear fade used to keep identity text readable over character art."""
    w, h = size
    layer = Image.new("RGBA", (max(1, w // 4), max(1, h // 4)), (0, 0, 0, 0))
    pixels = layer.load()
    small_w, small_h = layer.size
    for y in range(small_h):
        for x in range(small_w):
            if horizontal:
                t = x / max(small_w - 1, 1)
                alpha = round(226 * (1 - t) ** 0.85)
            else:
                t = y / max(small_h - 1, 1)
                alpha = round(180 * t ** 1.1)
            pixels[x, y] = (12, 8, 23, alpha)
    return layer.resize((w, h), Image.Resampling.BILINEAR)


def header_art(canvas, data: SkillData, width: int, height: int) -> None:
    """Composite scaled character art and readability scrims into the header, keeping space for stats panels."""
    if not data.splash:
        return
    image = trimmed_splash(data.splash)
    target_h = height + 18
    scale = target_h / image.height
    resized = image.resize((round(image.width * scale), target_h), Image.Resampling.LANCZOS)
    # Sit the art in the gap between the identity text and the stats panel
    # instead of flush against the left edge, where it collided with the copy.
    max_width = 470
    if resized.width > max_width:
        ratio = max_width / resized.width
        resized = resized.resize((max_width, round(resized.height * ratio)), Image.Resampling.LANCZOS)
    art_x = 812 - resized.width
    art_y = height - resized.height + 26
    canvas.alpha_composite(radial((700, 700), (246, 172, 87, 0.18)), (art_x + 20, art_y + 40))
    canvas.alpha_composite(resized, (art_x, art_y))
    canvas.alpha_composite(scrim((780, height), horizontal=True), (0, 0))
    canvas.alpha_composite(scrim((780, height), horizontal=False), (0, 0))


def stat_icon(data: SkillData, name: str | None, size: int = 18) -> Image.Image | None:
    """Read a cached stat icon at size square pixels, or None when unnamed/missing."""
    if not name:
        return None
    return load_webp(data.skill_icon_dir / name, (size, size))


def draw_identity(canvas, draw, data: SkillData, width: int, height: int) -> None:
    """Draw the localized name, rarity, element/path labels and bounded description into the header."""
    text_w = 556
    title = data.name.upper() if data.locale == "en" else data.name
    title_size = 48
    while title_size > 34 and draw.textlength(
        title, font=font(title_size, bold=True, display=True, locale=data.locale)
    ) > text_w:
        title_size -= 2
    if any(ord(char) > 127 for char in title):
        title_font = font_w(title_size, WEIGHT_BOLD, data.locale, title)
    else:
        title_font = font(title_size, bold=True, display=True, locale=data.locale)
    y = 72
    for line in wrap_locale(draw, title, title_font, text_w, data.locale)[:2]:
        draw.text((M, y), line, font=title_font, fill=TEXT)
        y += round(title_size * 1.12)
    y += 8
    for index in range(data.stars):
        make_star(canvas, M + 12 + index * 25, y + 9, 10, GOLD)
    y += 29
    tag_x = M
    for label, icon, color in (
        (data.element_label.upper(), data.element_icon, FIRE),
        (data.path_label.upper(), data.path_icon, PURPLE),
    ):
        fnt = font(12, bold=True, locale=data.locale)
        tag_w = draw.textlength(label, font=fnt) + 40
        composite_panel(canvas, (tag_x, y, tag_x + tag_w, y + 30), 15, (*color[:3], 42), (*color[:3], 132))
        if icon:
            canvas.alpha_composite(icon.resize((20, 20), Image.Resampling.LANCZOS), (round(tag_x) + 10, round(y) + 5))
            draw.text((tag_x + 37, y + 7), label, font=fnt, fill=color)
        else:
            draw.text((tag_x + 18, y + 7), label, font=fnt, fill=color)
        tag_x += tag_w + 9
    if data.description:
        desc_font = font(15, locale=data.locale)
        y += 42
        for line in wrap_locale(draw, data.description, desc_font, text_w, data.locale)[:3]:
            draw_text_runs(draw, line, M, y, 15, WEIGHT_REGULAR, BODY_SOFT, data.locale)
            y += 20


def format_stat_value(value: float, *, comma: bool = False) -> str:
    """Format a base stat compactly, or as a comma-grouped whole value when comma=True."""
    if comma:
        return f"{value:,.0f}"
    return f"{value:g}"


def stat_pair(value: str, previous: str | None) -> str:
    """Return previous-to-current display text only when a previous value exists and differs."""
    if previous is None or previous == value:
        return value
    return f"{previous} \u2192 {value}"


def draw_stat_panel(canvas, draw, data: SkillData, x: int, y: int, width: int, height: int) -> None:
    """Draw level-80 stats in pixel bounds, showing previous values and tinting changed comparison rows."""
    composite_panel(canvas, (x, y, x + width, y + height), 20, (19, 14, 33, 236), (255, 255, 255, 40))
    draw.text((x + 22, y + 16), ui(data, "base_stats"), font=font_w(12, WEIGHT_BOLD, data.locale), fill=PURPLE)
    draw.text(
        (x + width - 22 - draw.textlength("LV. 80", font=font_w(11, WEIGHT_SEMI, data.locale)), y + 17),
        "LV. 80",
        font=font_w(11, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
    draw.line((x + 22, y + 42, x + width - 22, y + 42), fill=LINE, width=1)
    stats = data.stats
    before = data.stats_before
    specs = [
        ("hp", ui(data, "base_hp"), "IconMaxHP.webp", True),
        ("atk", ui(data, "base_atk"), "IconAttack.webp", True),
        ("def", ui(data, "base_def"), "IconDefence.webp", True),
        ("spd", ui(data, "base_spd"), "IconSpeed.webp", False),
        ("aggro", ui(data, "taunt"), None, False),
        (None, ui(data, "max_energy"), None, False),
    ]
    rows = max(1, len(specs))
    row_h = (height - 52) / rows
    for index, (key, label, icon_name, comma) in enumerate(specs):
        ry = y + 50 + index * row_h
        if key is None:
            value = format_stat_value(data.sp_need, comma=False)
            previous_value = (
                format_stat_value(data.sp_need_before, comma=False)
                if data.sp_need_before not in (None, data.sp_need)
                else None
            )
        else:
            value = format_stat_value(stats.get(key, 0), comma=comma)
            previous_value = (
                format_stat_value(before[key], comma=comma)
                if before is not None and before.get(key) != stats.get(key)
                else None
            )
        icon = stat_icon(data, icon_name, 18)
        text_x = x + 24
        if icon:
            canvas.alpha_composite(icon, (x + 22, round(ry) - 2))
            text_x = x + 48
        draw.text((text_x, ry), label, font=font_w(13, WEIGHT_SEMI, data.locale), fill=MUTED)
        text = stat_pair(value, previous_value)
        value_font = font_w(14, WEIGHT_BOLD, data.locale)
        value_w = draw.textlength(text, font=value_font)
        value_color = GOLD if previous_value else TEXT
        draw.text((x + width - 22 - value_w, ry - 1), text, font=value_font, fill=value_color)
        if index < rows - 1:
            draw.line((x + 22, ry + row_h - 7, x + width - 22, ry + row_h - 7), fill=(255, 255, 255, 18), width=1)
        if previous_value:
            change_overlay(canvas, (x + 12, ry - 6, x + width - 12, ry + row_h - 4), radius=8)


def bonus_icon_name(label: str) -> str | None:
    """Map an English minor-trace bonus label to its cached icon filename; unknown labels return None."""
    return {
        "HP": "IconMaxHP.webp",
        "ATK": "IconAttack.webp",
        "DEF": "IconDefence.webp",
        "SPD": "IconSpeed.webp",
        "CRIT Rate": "IconCriticalChance.webp",
        "CRIT DMG": "IconCriticalDamage.webp",
        "Fire DMG Boost": "IconFireAddedRatio.webp",
        "Ice DMG Boost": "IconIceAddedRatio.webp",
        "Wind DMG Boost": "IconWindAddedRatio.webp",
        "Lightning DMG Boost": "IconThunderAddedRatio.webp",
        "Physical DMG Boost": "IconPhysicalAddedRatio.webp",
        "Quantum DMG Boost": "IconQuantumAddedRatio.webp",
        "Imaginary DMG Boost": "IconImaginaryAddedRatio.webp",
    }.get(label)


def draw_bonus_panel(canvas, draw, data: SkillData, x: int, y: int, width: int, height: int) -> None:


    """Draw minor-trace bonus tiles in pixel bounds, preserving flat values and highlighting comparisons."""
    composite_panel(canvas, (x, y, x + width, y + height), 20, (19, 14, 33, 236), (255, 255, 255, 40))
    draw.text((x + 22, y + 16), ui(data, "total_bonus"), font=font_w(12, WEIGHT_BOLD, data.locale), fill=PURPLE)
    subtitle = "MINOR TRACES"
    draw.text(
        (x + width - 22 - draw.textlength(subtitle, font=font_w(10, WEIGHT_SEMI, data.locale)), y + 17),
        subtitle,
        font=font_w(10, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
    draw.line((x + 22, y + 42, x + width - 22, y + 42), fill=LINE, width=1)

    old = {label: (value, property_type) for label, value, property_type in (data.bonuses_before or [])}
    labels = [label for label, _, _ in data.bonuses]
    labels.extend(label for label in old if label not in labels)
    rows = labels[:6]
    columns = 3
    tile_gap = 12
    inner_w = width - 44
    tile_w = (inner_w - tile_gap * (columns - 1)) / columns
    tile_h = 86
    for index, label in enumerate(rows):
        col = index % columns
        row = index // columns
        bx = x + 22 + col * (tile_w + tile_gap)
        by = y + 56 + row * (tile_h + 10)
        current = next(
            ((value, property_type) for name, value, property_type in data.bonuses if name == label),
            None,
        )
        previous = old.get(label)
        changed = current is None or (previous is not None and previous[0] != current[0])
        tile_fill = (142, 216, 168, 20) if changed else (255, 255, 255, 16)
        tile_edge = (142, 216, 168, 64) if changed else (255, 255, 255, 24)
        composite_panel(canvas, (bx, by, bx + tile_w, by + tile_h), 14, tile_fill, tile_edge)
        icon = stat_icon(data, bonus_icon_name(label), 16)
        label_x = bx + 14
        if icon:
            canvas.alpha_composite(icon, (round(bx + 12), round(by + 12)) )
            label_x = bx + 34
        draw.text(
            (label_x, by + 12),
            fit(draw, label.upper(), font_w(10, WEIGHT_SEMI, data.locale), tile_w - (label_x - bx) - 12),
            font=font_w(10, WEIGHT_SEMI, data.locale),
            fill=MUTED,
        )
        if current is None:
            value_text = format_bonus(*previous)
            value_color = (224, 150, 164, 255)
        else:
            value_text = format_bonus(*current)
            value_color = TEXT
        draw.text((bx + 14, by + 34), value_text, font=font_w(24, WEIGHT_BOLD, data.locale, value_text), fill=value_color)
        if current is not None and previous is not None and previous[0] != current[0]:
            draw.text(
                (bx + 14, by + tile_h - 22),
                f"was {format_bonus(*previous)}",
                font=font_w(9, WEIGHT_SEMI, data.locale),
                fill=(224, 150, 164, 230),
            )


def header(canvas, draw, data: SkillData, width: int, height: int):
    """Draw the complete identity/art/stats/bonus header into the provided canvas dimensions."""
    draw.rectangle((0, 0, width, height), fill=(12, 8, 23, 255))
    header_art(canvas, data, width, height)
    draw.line((M, 64, width - M, 64), fill=LINE, width=1)
    header_label = ui(data, "header")
    if data.comparison:
        header_label = f"{header_label}  /  VERSION COMPARISON"
    draw.text(
        (M, 27),
        f"NANOKA / HSR  /  {header_label}",
        font=font(14, bold=True, locale=data.locale),
        fill=MUTED,
    )
    version_pill(canvas, draw, data, width)
    draw_identity(canvas, draw, data, width, height)

    stats_x = 828
    stats_w = 456
    bonus_x = stats_x + stats_w + 18
    bonus_w = width - M - bonus_x
    panel_y = 82
    panel_h = height - panel_y - 48
    draw_stat_panel(canvas, draw, data, stats_x, panel_y, stats_w, panel_h)
    draw_bonus_panel(canvas, draw, data, bonus_x, panel_y, bonus_w, panel_h)

    if data.comparison:
        draw.text(
            (M, height - 26),
            f"OLD v{data.version_before} struck/removed  \u00b7  NEW v{data.version_after} highlighted",
            font=font(9, bold=True, locale=data.locale),
            fill=DIM,
        )
    else:
        draw.text(
            (M, height - 26),
            ui(data, "levels"),
            font=font(9, bold=True, locale=data.locale),
            fill=DIM,
        )


def section_title(draw, x: int, y: int, title: str, subtitle: str, width: int, locale: str, size: int = 20) -> int:
    """Draw a localized section heading/subtitle and divider; return the divider's y coordinate."""
    draw.rectangle((x, y + 6, x + 24, y + 10), fill=PURPLE)
    draw.text((x + 34, y - 4), title, font=font(size, bold=True, locale=locale), fill=PURPLE)
    if subtitle:
        sub = font(10, bold=True, locale=locale)
        sub_w = draw.textlength(subtitle, font=sub)
        draw.text((x + width - sub_w, y + 1), subtitle, font=sub, fill=DIM)
    draw.line((x, y + 33, x + width, y + 33), fill=LINE, width=1)
    return y + 33


def footer_version(data: SkillData) -> str:
    """Return the single or older-to-newer build label used in the footer."""
    if data.comparison:
        return f"v{data.version_before} \u2192 v{data.version_after}"
    return f"v{data.version}"


def draw_footer(draw, width: int, height: int, data: SkillData, page: str):
    """Draw version/locale provenance and the page label along the canvas bottom."""
    draw.line((M, height - 42, width - M, height - 42), fill=LINE, width=1)
    draw.text(
        (M, height - 29),
        f"NANOKA HSR  /  DATA {footer_version(data)}  /  {data.locale.upper()}",
        font=font_w(10, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
    page_w = draw.textlength(page, font=font_w(10, WEIGHT_SEMI, data.locale))
    draw.text(
        (width - M - page_w, height - 29),
        page,
        font=font_w(10, WEIGHT_SEMI, data.locale),
        fill=DIM,
    )
