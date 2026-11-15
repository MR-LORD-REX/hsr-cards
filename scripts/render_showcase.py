"""Render public documentation examples without loading credentials or player records.

Run with the project's virtual environment: ``python scripts/render_showcase.py``.
The Nanoka cache and cached Prydwen HTML must already exist. This script uses
real catalog data/artwork and clearly marked, fictional HoYoLAB sample records.
Generated PNG originals go to Cards; smaller WebP previews are served by Pages.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image
from hsr_cards import HonkaiStarrail, NanokaClient, PrydwenClient

VERSION = "4.7.51"
CACHE = ROOT / ".nanoka_cache"
ASSETS = CACHE / VERSION / "en" / "assets"
PNG_DIR = ROOT / "Cards"
PREVIEW_DIR = ROOT / "docs" / "assets" / "showcase"
MANIFEST = ROOT / "docs" / "data" / "showcase.json"
RAW_URL = "https://raw.githubusercontent.com/MR-LORD-REX/hsr-cards/main/Cards/"
ANCHORS = {
    "get_character_info-blade-mortenax": ["character-info"],
    "get_current_endgame_card-moc-floor-12": ["endgame-current"],
    "get_current_endgame_card-pf-floor-4": ["current-pf"],
    "get_current_endgame_card-as-floor-4": ["current-as"],
    "moc-sample": ["player-moc"],
    "prydwen-card-acheron-draft": ["build-card"],
    "tier_list-moc-snapshot": ["tier-list-moc"],
}


def image_of(result):
    """Extract the first image from a public single, floor, or batch result."""
    if isinstance(result, Image.Image):
        return result
    if isinstance(result, list):
        return image_of(result[0])
    if hasattr(result, "image"):
        return result.image
    if hasattr(result, "cards"):
        return result.cards[0].image
    if hasattr(result, "succeeded"):
        if not result.succeeded:
            raise RuntimeError(str(result.errors))
        return result.succeeded[0].image
    raise TypeError(f"Unsupported showcase result {type(result)}")


class Showcase:
    """Write verified images and keep a resumable website/gallery manifest."""

    def __init__(self):
        for directory in (PNG_DIR, PREVIEW_DIR, MANIFEST.parent):
            directory.mkdir(parents=True, exist_ok=True)
        self.data = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {
            "generated_at": str(date.today()), "items": [], "unavailable": []
        }

    def save(self, result, *, id, method, title, group, source, description, example):
        image = image_of(result).convert("RGB")
        if image.width < 250 or image.height < 150:
            raise ValueError(f"Suspiciously small output: {id} {image.size}")
        png = PNG_DIR / f"showcase-{id}.png"
        image.save(png, optimize=True)
        with Image.open(png) as saved:
            saved.verify()
        preview = image.copy()
        preview.thumbnail((1280, 6000), Image.Resampling.LANCZOS)
        name = f"showcase-{id}.webp"
        preview.save(PREVIEW_DIR / name, quality=84, method=6)
        entry = {
            "id": id, "method": method, "title": title, "group": group,
            "image": f"assets/showcase/{name}", "original": RAW_URL + png.name,
            "source": source, "description": description,
            "width": image.width, "height": image.height, "example": example,
        }
        self.data["items"] = [x for x in self.data["items"] if x["id"] != id] + [entry]
        self.data["unavailable"] = [x for x in self.data["unavailable"] if x["method"] != method]
        self.flush()
        print(f"Rendered {id}: {image.width} x {image.height}", flush=True)

    def failed(self, method, exc):
        self.data["unavailable"] = [x for x in self.data["unavailable"] if x["method"] != method]
        self.data["unavailable"].append({"method": method, "reason": str(exc)})
        self.flush()
        print(f"Unavailable {method}: {exc}", flush=True)

    def flush(self):
        self.data["generated_at"] = str(date.today())
        for item in self.data["items"]:
            item["anchors"] = ANCHORS.get(item["id"], [])
        self.data["items"].sort(key=lambda x: (x["group"], x["method"], x["id"]))
        MANIFEST.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        text = [
            "# Card showcase", "",
            "Fresh demo outputs from the public card methods. Open the [interactive showcase](index.html#/showcase) to filter by provider and method, or select a PNG below for the original resolution.", "",
            "Nanoka examples use cached public catalog data from build `4.7.51`. HoYoLAB examples use fictional, nonpersonal sample payloads with cached public artwork; their dates, teams and scores illustrate the layout. Prydwen build demos retain their source provenance and draft status where applicable. These are documentation snapshots, not live account records or a promise of current rankings.", "",
            "Recreate the gallery with `python scripts/render_showcase.py --live-tiers` from the repository root, after populating the public data/artwork caches. Omitting `--live-tiers` uses a local MOC parser fixture instead of fetching rankings. The script never reads `.env` or authenticates a player account.", "",
        ]
        for item in self.data["items"]:
            for anchor in item["anchors"]:
                text += [f'<a id="{anchor}"></a>', ""]
            text += [f"## {item['title']}", "", f"`{item['method']}` · {item['width']} × {item['height']}", "",
                     item["description"], "", f"**Source:** {item['source']}", "",
                     f"[![{item['title']}]({item['image']})]({item['original']})", "",
                     "```python", item["example"], "```", ""]
        text += ["## Methods without image output", "",
                 "Provider queries, verification, cache updates, parsing, approval, validation, lifecycle methods and properties return data or manage resources. Their usage is documented in the API guides. AA Nanoka floor cards remain deferred; the supported player `anomaly()` card is shown above.", ""]
        if self.data["unavailable"]:
            text += ["## Unavailable examples", ""]
            text += [f"- `{x['method']}`: {x['reason']}" for x in self.data["unavailable"]]
            text += [""]
        (ROOT / "docs" / "showcase.md").write_text("\n".join(text), encoding="utf-8")


async def nanoka_examples(showcase):
    """Call catalog, comparison, floor and batch methods against public caches."""
    nanoka = NanokaClient(version=VERSION, cache_dir=CACHE, include_assets=False)
    async with HonkaiStarrail(nanoka_client=nanoka) as client:
        common = {"cache_dir": str(CACHE), "use_rendered_cache": False}
        specs = [
            ("get_character_info", 1507, VERSION, "blade-mortenax", "Character information", "Character art, ascension materials and level-80 stats."),
            ("get_character_skills", 1511, ("4.6.51", "4.6.54"), "aha-comparison", "Character skills comparison", "Skills, traces and eidolons compared between two public builds."),
            ("get_LC_info", 23066, VERSION, "23066", "Light Cone information", "Level-80 Light Cone stats with S1–S5 descriptions."),
            ("get_relic_info", 134, VERSION, "134", "Relic set information", "Relic pieces, artwork and set bonuses."),
            ("get_item_info", 223, VERSION, "223", "Item information", "Public item descriptions and obtain sources."),
        ]
        for method, identifier, version, variant, title, description in specs:
            try:
                result = await getattr(client, method)(identifier, version, **common)
                showcase.save(result, id=f"{method.lower()}-{variant}", method=f"HonkaiStarrail.{method}", title=title,
                              group="Nanoka", source=f"Nanoka public catalog; version {version!r}", description=description,
                              example=f'result = await client.{method}({identifier}, {version!r})\nresult.image.save("{method}.png")')
            except Exception as exc:
                showcase.failed(f"HonkaiStarrail.{method}", exc)
        for method in ("get_current_endgame_card", "get_next_endgame_card"):
            for mode in ("MOC", "PF", "AS"):
                floor = 12 if mode == "MOC" else 4
                try:
                    result = await getattr(client, method)(mode, floors=floor, use_rendered_cache=False)
                    showcase.save(result, id=f"{method}-{mode.lower()}-floor-{floor}", method=f"HonkaiStarrail.{method}",
                                  title=f"{'Current' if 'current' in method else 'Next'} {mode} · Floor {floor}", group="Nanoka",
                                  source=f"Nanoka {result.version}; season {result.season_id}: {result.season_name}",
                                  description="Enemies, mechanics and buffs for a complete endgame floor. Current/next selection uses the renderer's generation date.",
                                  example=f'result = await client.{method}("{mode}", floors={floor})\nresult.cards[0].image.save("{mode.lower()}-floor-{floor}.png")')
                except Exception as exc:
                    showcase.failed(f"HonkaiStarrail.{method}({mode})", exc)
        for method in ("render_all_info", "render_all_skills"):
            try:
                result = await getattr(client, method)(VERSION, identifiers=[1507], concurrency=1, **common)
                showcase.save(result, id=f"{method}-blade-mortenax", method=f"HonkaiStarrail.{method}",
                              title=f"Batch {'information' if 'info' in method else 'skills'} rendering", group="Nanoka",
                              source=f"Nanoka {VERSION}; a one-character batch", description="One successful card from the batch result. Each character retains its own outcome and error.",
                              example=f'batch = await client.{method}("{VERSION}", identifiers=[1507])\nfor item in batch.succeeded:\n    item.image.save(f"{{item.identifier}}.png")')
            except Exception as exc:
                showcase.failed(f"HonkaiStarrail.{method}", exc)
        for detailed in (False, True):
            try:
                result = await client.character_build("Acheron", detailed=detailed)
                if result is None:
                    raise ValueError("The approved Acheron build variant is missing")
                showcase.save(result, id=f"character_build-acheron-{'detailed' if detailed else 'clean'}", method="HonkaiStarrail.character_build",
                              title=f"Acheron build · {'Detailed' if detailed else 'Clean'}", group="Prydwen",
                              source="Approved repository Prydwen build assets; retrieved through the public facade",
                              description="The public method returns an approved build image. Detailed mode also returns the available condition pages; this preview shows the summary.",
                              example=f'build = await client.character_build("Acheron", detailed={detailed})\n' + ('build[0].save("acheron-detailed.png")' if detailed else 'build.save("acheron.png")'))
            except Exception as exc:
                showcase.failed(f"HonkaiStarrail.character_build(detailed={detailed})", exc)
    await nanoka.close()


async def hoyolab_examples(showcase):
    """Render fictional player/calendar records through the public facade."""
    from showcase.samples import SampleHoYoLAB, local_artwork
    with local_artwork():
        async with HonkaiStarrail(hoyolab_client=SampleHoYoLAB()) as client:
            for method, title in (("anomaly", "Anomaly Arbitration record"), ("MOC", "Memory of Chaos record"),
                                  ("PF", "Pure Fiction record"), ("shadow", "Apocalyptic Shadow record"),
                                  ("banners", "Warp schedule"), ("events", "Event calendar"),
                                  ("endgame", "Endgame schedule"), ("notes", "Daily notes"),
                                  ("currency_war", "Currency Wars run")):
                try:
                    result = await getattr(client, method)()
                    showcase.save(result, id=f"{method.lower()}-sample", method=f"HonkaiStarrail.{method}", title=title,
                                  group="HoYoLAB", source="Fictional documentation sample; cached public artwork",
                                  description="Illustrative output rendered by the public method. Dates, progress, teams and scores are sample values and do not belong to a player account." + (" The MOC sample shows floors 10–12." if method == "MOC" else " The AS sample shows floors 2–4." if method == "shadow" else ""),
                                  example=f'image = await client.{method}()\n' + ('image.image.save("currency-war.png")' if method == "currency_war" else f'image.save("{method.lower()}.png")'))
                except Exception as exc:
                    showcase.failed(f"HonkaiStarrail.{method}", exc)


async def prydwen_examples(showcase, *, live_tiers=False):
    """Render cached public build drafts using the standalone client."""
    with tempfile.TemporaryDirectory(prefix="hsr-showcase-") as working:
        work = Path(working)
        client = PrydwenClient(work_dir=work, build_dir=work / "published", nanoka_cache=CACHE, nanoka_version=VERSION)
        client.raw_dir.mkdir(parents=True)
        for name in ("acheron.html", "acheron.meta.json"):
            source = ROOT / ".hsr_prydwen" / "raw" / name
            if source.is_file():
                shutil.copyfile(source, client.raw_dir / name)
        try:
            parsed = client.parse("acheron")
            if parsed["failed"] or not parsed["paths"]:
                raise ValueError(str(parsed["failed"]))
            for method in ("card", "cards"):
                if method == "card":
                    output = client.card("acheron", allow_draft=True)
                else:
                    rendered = client.cards(["acheron"], allow_draft=True)
                    if rendered.get("failed"):
                        raise ValueError(str(rendered["failed"]))
                    output = work / "cards" / "acheron.png"
                showcase.save(Image.open(output), id=f"prydwen-{method}-acheron-draft", method=f"PrydwenClient.{method}",
                              title=f"Prydwen {'single build' if method == 'card' else 'batch build'} rendering", group="Prydwen",
                              source="Cached public Prydwen Acheron HTML, parsed as a draft; no approval or publication",
                              description="Fresh rendering of a cached source snapshot through the standalone build pipeline. Draft status is retained and the render uses Nanoka artwork.",
                              example=f'with_data = client.parse("acheron")\n' + ('path = client.card("acheron", allow_draft=True)' if method == "card" else 'result = client.cards(["acheron"], allow_draft=True)'))
        except Exception as exc:
            showcase.failed("PrydwenClient.card/cards", exc)
        finally:
            await client.close()
    from hsr_cards.providers.prydwen.parsing.tiers import parse_tier_list
    from hsr_cards.renderer.prydwen.tier_list import TierListRenderer
    from hsr_cards.providers.prydwen.assets import NanokaIndex
    from showcase.samples import open_local
    index = NanokaIndex(CACHE, VERSION)
    modes = ("MOC", "PF", "AS") if live_tiers else ("MOC",)
    async with PrydwenClient(nanoka_cache=CACHE, nanoka_version=VERSION) as public:
        for mode in modes:
            try:
                if live_tiers:
                    data = await public.get_tier_list(game_mode=mode, timeout=20)
                    source = f"Public Prydwen {mode} tier list fetched {date.today()}; source update: {data.updated}"
                    description = "Fresh public tier-list snapshot with role columns, character tags and ranking-change marks. Rankings can change after this documentation image was generated."
                else:
                    tier_source = ROOT / "tests" / "fixtures" / "prydwen_tier_list.html"
                    data = parse_tier_list(tier_source.read_text(encoding="utf-8"))
                    source = "Prydwen parser fixture snapshot; illustrative rankings, not a live tier list"
                    description = "The real tier renderer receives a parsed fixture snapshot. This compact example demonstrates the grid and tags; call the public method normally to fetch current rankings."
                portraits = {}
                for tier in data.tiers:
                    for role in tier.roles:
                        for character in role.characters:
                            identifier = index.character_id(name=character.name, slug=character.slug)
                            if identifier is None:
                                raise FileNotFoundError(f"No unambiguous cached tier portrait for {character.name} ({character.slug})")
                            portraits[character.icon_url] = ASSETS / "avatarshopicon" / f"{identifier}.webp"

                class SnapshotPrydwen:
                    async def get_tier_list(self, **kwargs):
                        return data

                async def tier_art(renderer, url):
                    return open_local(portraits[url])

                with patch.object(TierListRenderer, "_fetch_image", tier_art):
                    async with HonkaiStarrail(prydwen_client=SnapshotPrydwen()) as client:
                        result = await client.tier_list(mode)
                showcase.save(result, id=f"tier_list-{mode.lower()}-snapshot", method="HonkaiStarrail.tier_list", title=f"{data.mode} tier list", group="Prydwen",
                              source=source, description=description,
                              example=f'image = await client.tier_list("{mode}")\nimage.save("{mode.lower()}-tier-list.png")')
            except Exception as exc:
                showcase.failed(f"HonkaiStarrail.tier_list({mode})", exc)
    # Old interrupted attempts used an unqualified method name.
    if any(x["method"] == "HonkaiStarrail.tier_list" for x in showcase.data["items"]):
        showcase.data["unavailable"] = [x for x in showcase.data["unavailable"] if x["method"] != "HonkaiStarrail.tier_list"]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("all", "nanoka", "hoyolab", "prydwen"), default="all")
    parser.add_argument("--live-tiers", action="store_true", help="Fetch public mode-specific Prydwen rankings instead of the local MOC parser fixture.")
    args = parser.parse_args()
    if not ASSETS.is_dir():
        parser.error(f"Populate the public Nanoka {VERSION} cache before rendering: {ASSETS}")
    showcase = Showcase()
    for group, render in (("nanoka", nanoka_examples), ("hoyolab", hoyolab_examples), ("prydwen", prydwen_examples)):
        if args.group in ("all", group):
            if group == "prydwen":
                await render(showcase, live_tiers=args.live_tiers)
            else:
                await render(showcase)
    showcase.flush()
    print(f"Gallery: {len(showcase.data['items'])} previews; {len(showcase.data['unavailable'])} unavailable", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
