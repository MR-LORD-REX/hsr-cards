"""Legacy command-line rendering and file output for character info variants."""
from __future__ import annotations

from pathlib import Path
import argparse
import asyncio
from hsr_cards.renderer.nanoka.info.rendering import render_detail, render_hero, render_materials
from hsr_cards.services.character_info import load_data


async def build_all(character_id: int, locale: str, output_dir: Path, with_voice: bool = False):
    """Load the newest character build and write hero/material/detail card variants.

    character_id is numeric and locale selects Nanoka language. output_dir is created
    as needed; named PNG outputs are replaced and file paths/sizes are printed.
    with_voice is retained for renderer compatibility. The operation-created client
    is closed after successful writes; loading/render/file errors propagate.
    """
    data, character = await load_data(character_id, locale)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if locale == "en" else f"_{locale}"
    variants = {
        f"character_{character_id}_hero_1080x1250{suffix}.png": render_hero(data),
        f"character_{character_id}_materials_1080x1250{suffix}.png": render_materials(data),
        f"character_{character_id}_detail_1080x1440{suffix}.png": render_detail(data, with_voice=with_voice),
    }
    for name, image in variants.items():
        path = output_dir / name
        image.convert("RGB").save(path, quality=95, subsampling=0)
        print(f"{path} ({path.stat().st_size:,} bytes)")
    await character.client.close()


def main():
    """Parse character ID, locale, output directory and the compatibility voice flag, then run the async info writer."""
    parser = argparse.ArgumentParser()
    parser.add_argument("character_id", type=int)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--with-voice", action="store_true", help="Accepted for compatibility; voice cast is always in the detail panel")
    args = parser.parse_args()
    asyncio.run(build_all(args.character_id, args.locale, args.out))
