"""Verify gallery metadata/images and produce temporary sheets for visual QA."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont, ImageStat


def main():
    manifest = json.loads((ROOT / "docs/data/showcase.json").read_text(encoding="utf-8"))
    temporary = Path(tempfile.mkdtemp(prefix="hsr-showcase-qa-"))
    for group in ("HoYoLAB", "Nanoka", "Prydwen"):
        items = [item for item in manifest["items"] if item["group"] == group]
        sheet = Image.new("RGB", (1080, ((len(items) + 2) // 3) * 480), (18, 20, 28))
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default(size=13)
        for index, item in enumerate(items):
            png = ROOT / "Cards" / item["original"].rsplit("/", 1)[1]
            with Image.open(png) as opened:
                assert opened.size == (item["width"], item["height"]), item["id"]
                original = opened.convert("RGB")
                assert max(ImageStat.Stat(original).stddev) > 5, item["id"]
            with Image.open(ROOT / "docs" / item["image"]) as preview:
                preview.verify()
            original.thumbnail((338, 432), Image.Resampling.LANCZOS)
            x, y = index % 3 * 360, index // 3 * 480
            sheet.paste(original, (x + (360 - original.width) // 2, y + 34))
            draw.text((x + 10, y + 8), item["id"][:45], font=font, fill="white")
            draw.text((x + 10, y + 462), f'{item["width"]} × {item["height"]}', font=font, fill=(150, 164, 190))
        target = temporary / f"{group.lower()}-contact-sheet.png"
        sheet.save(target)
        print(target)
    assert not manifest["unavailable"], manifest["unavailable"]
    methods = {item["method"] for item in manifest["items"]}
    expected = {f"HonkaiStarrail.{name}" for name in (
        "anomaly", "MOC", "PF", "shadow", "banners", "events", "endgame", "notes", "currency_war",
        "get_character_info", "get_character_skills", "get_LC_info", "get_relic_info", "get_item_info",
        "get_current_endgame_card", "get_next_endgame_card", "render_all_info", "render_all_skills",
        "character_build", "tier_list",
    )} | {"PrydwenClient.card", "PrydwenClient.cards"}
    assert methods == expected, f"Missing: {expected - methods}; unexpected: {methods - expected}"
    print(f'Verified {len(manifest["items"])} PNG/WebP pairs covering {len(methods)} image-returning methods.')


if __name__ == "__main__":
    main()
