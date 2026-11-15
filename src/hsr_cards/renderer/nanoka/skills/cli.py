"""Legacy command-line rendering and file output for character skills."""
from __future__ import annotations

from pathlib import Path
import argparse
import asyncio
import json
from hsr_cards.renderer.nanoka.skills.rendering import render_eidolon_page, render_full, render_skill_page, render_summary
from hsr_cards.services.skills import load_data


async def build(character_id: int, locale: str, variant: str, output: Path, json_output: bool = False):
    """Load and write full, summary or paged skills cards for a numeric character ID.

    locale selects the newest-build data language. output supplies the destination
    directory/name template; optional json_output writes rich payloads for full cards.
    Create directories, overwrite output files and print their paths/dimensions.
    The temporary client is closed after successful writes; provider/file/render
    errors propagate. This coroutine is the legacy CLI implementation.
    """
    data, character = await load_data(character_id, locale)
    client = character.client
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = "" if locale == "en" else f"_{locale}"
    outputs = []
    if variant == "full":
        result = render_full(data)
        outputs.append((output.with_name(f"character_{character_id}_skills_full{suffix}.png"), result.image))
        if json_output:
            json_path = output.with_name(f"character_{character_id}_skills_tables{suffix}.json")
            json_path.write_text(
                json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"{json_path} | {len(result.tables)} tables | {len(result.dropdowns)} dropdowns")
    elif variant == "summary":
        outputs.append((output.with_name(f"character_{character_id}_skills_summary{suffix}.png"), render_summary(data)))
    else:
        pages = [data.skills[index:index + 6] for index in range(0, len(data.skills), 6)]
        for index, skills in enumerate(pages, start=1):
            outputs.append(
                (
                    output.with_name(f"character_{character_id}_skills_pages_{index}{suffix}.png"),
                    render_skill_page(data, skills, index, len(pages) + 1),
                )
            )
        outputs.append(
            (output.with_name(f"character_{character_id}_eidolons_pages{suffix}.png"), render_eidolon_page(data))
        )
    for path, image in outputs:
        image.convert("RGB").save(path, quality=94, subsampling=0)
        print(f"{path} | {image.width}x{image.height} | {path.stat().st_size:,} bytes")
    print(f"skills={len(data.skills)} | eidolons={len(data.eidolons)}")
    await client.close()


def main():
    """Parse numeric ID, locale, variant/output/JSON command-line options and run the async skills writer."""
    parser = argparse.ArgumentParser()
    parser.add_argument("character_id", type=int)
    parser.add_argument("--locale", default="en")
    parser.add_argument("--variant", choices=("full", "summary", "pages"), default="full")
    parser.add_argument("--out", type=Path, default=Path("out") / "skills.png")
    parser.add_argument("--json", action="store_true", help="Write the tables/dropdowns payload alongside the card")
    args = parser.parse_args()
    asyncio.run(build(args.character_id, args.locale, args.variant, args.out, args.json))
