"""Resolve and load only the artwork used by an endgame floor card."""
from __future__ import annotations
import asyncio
from pathlib import Path
from PIL import Image
from ...nanoka import NanokaClient
from ...nanoka.models import MonsterDetail
from .models import FloorCardData


def monster_asset(identifier: int, detail: MonsterDetail | None) -> str:
    """Use Nanoka's artwork stem; boss variants often share a base icon."""
    if detail is not None and detail.image_path:
        stem = Path(detail.image_path.replace("\\", "/")).stem
    else:
        stem = f"Monster_{detail.id if detail is not None else identifier}"
    return f"monstermiddleicon/{stem}.webp"


def load_icon(client: NanokaClient, relative: str) -> Image.Image | None:
    """Decode one cached CDN-relative icon as an RGBA image without downloading it.

    Return None for missing, corrupt or unreadable files. The supplied provider client
    is borrowed; its cache path is read and its lifecycle is unchanged.
    """
    path = client.cache.asset_file(relative)
    if not path.is_file():
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGBA")
    except (OSError, ValueError):
        return None


async def load_assets(client: NanokaClient, data: FloorCardData) -> None:
    """Fill missing monster/corrosion artwork on resolved FloorCardData in place.

    Fetch unique CDN-relative assets concurrently through the supplied client, then
    read cached RGBA images. Missing optional icons remain None; provider failures
    propagate. The client stays caller-owned, and only its provider cache is written.
    """
    entries = [monster for node in data.nodes for wave in node.waves for monster in wave]
    entries.extend(target for node in data.nodes for target in node.corrosion_targets)
    missing = {entry.icon_asset for entry in entries if entry.icon is None and entry.icon_asset}
    await asyncio.gather(*(client.fetch_asset(relative) for relative in missing))
    for entry in entries:
        if entry.icon is None and entry.icon_asset:
            entry.icon = load_icon(client, entry.icon_asset)
