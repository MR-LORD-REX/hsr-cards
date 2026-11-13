"""Community build-guide cards bundled with ``hsr-cards``.

Images live in ``assets/char_builds`` as ``<character_id>.png`` and are
described by ``metadata.json``. The directory is scanned on each lookup so
``HonkaiStarrail.update_builds()`` can add or replace cards without a package
release.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image

from .utils.errors import HSR_Error

BUILD_REPO = "MR-LORD-REX/hsr-cards"
BUILD_BRANCH = "main"
BUILD_ASSET_PATH = "src/hsr_cards/assets/char_builds"
BUILD_METADATA_URL = (
    f"https://raw.githubusercontent.com/{BUILD_REPO}/{BUILD_BRANCH}/{BUILD_ASSET_PATH}/metadata.json"
)
BUILD_RAW_BASE = (
    f"https://raw.githubusercontent.com/{BUILD_REPO}/{BUILD_BRANCH}/{BUILD_ASSET_PATH}"
)
BUILD_TREE_BASE = f"https://github.com/{BUILD_REPO}/tree/{BUILD_BRANCH}/{BUILD_ASSET_PATH}"


def default_build_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "char_builds"


def build_raw_url(character_id: int | str) -> str:
    return f"{BUILD_RAW_BASE}/{character_id}.png"


def build_tree_url(character_id: int | str) -> str:
    return f"{BUILD_TREE_BASE}/{character_id}.png"


@dataclass(frozen=True)
class CharacterBuild:
    character_id: int
    char_name: str
    raw_url: str
    git_url: str
    path: Path

    def load(self) -> Image.Image:
        with Image.open(self.path) as image:
            return image.convert("RGB").copy()


def _normalise(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _matches_name(query: str, candidate: str) -> bool:
    needle = _normalise(query)
    name = _normalise(candidate)
    if not needle or not name:
        return False
    return needle == name or needle in name.split()


def _read_metadata(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_from_payload(root: Path, key: object, value: object) -> CharacterBuild | None:
    if not str(key).isdigit() or not isinstance(value, Mapping):
        return None
    character_id = int(str(key))
    char_name = value.get("char_name") or value.get("name") or str(character_id)
    return CharacterBuild(
        character_id=character_id,
        char_name=str(char_name),
        raw_url=str(value.get("raw_url") or build_raw_url(character_id)),
        git_url=str(value.get("git_url") or build_tree_url(character_id)),
        path=root / f"{character_id}.png",
    )


def scan_builds(build_dir: str | Path | None = None) -> list[CharacterBuild]:
    """Scan ``char_builds`` and merge ``metadata.json`` with the PNG files."""
    root = Path(build_dir).expanduser() if build_dir else default_build_dir()
    records: dict[int, CharacterBuild] = {}

    for key, value in _read_metadata(root / "metadata.json").items():
        record = _record_from_payload(root, key, value)
        if record is not None:
            records[record.character_id] = record

    if root.is_dir():
        for path in root.glob("*.png"):
            if not path.stem.isdigit():
                continue
            character_id = int(path.stem)
            if character_id in records:
                records[character_id] = replace(records[character_id], path=path)
            else:
                records[character_id] = CharacterBuild(
                    character_id=character_id,
                    char_name=str(character_id),
                    raw_url=build_raw_url(character_id),
                    git_url=build_tree_url(character_id),
                    path=path,
                )

    return sorted(records.values(), key=lambda record: record.character_id)


def find_build(
    identifier: int | str | None = None,
    *,
    name: str | None = None,
    search: str | None = None,
    build_dir: str | Path | None = None,
) -> CharacterBuild | None:
    """Find a build by character id, name, or Nanoka-style search text."""
    builds = scan_builds(build_dir)
    queries: list[str] = []

    if identifier is not None:
        if isinstance(identifier, int) or str(identifier).strip().isdigit():
            target = int(identifier)
            return next((build for build in builds if build.character_id == target), None)
        queries.append(str(identifier))
    if name:
        queries.append(name)
    if search:
        queries.append(search)

    for query in queries:
        for build in builds:
            if _matches_name(query, build.char_name):
                return build
    return None


def load_build_image(record: CharacterBuild | None) -> Image.Image | None:
    if record is None or not record.path.is_file():
        return None
    try:
        return record.load()
    except Exception as exc:
        raise HSR_Error(f"Could not read build image {record.path}: {exc}") from exc


def _write_metadata(path: Path, payload: Mapping) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


async def update_build_assets(
    session: aiohttp.ClientSession,
    *,
    metadata_url: str = BUILD_METADATA_URL,
    build_dir: str | Path | None = None,
    timeout: float = 30.0,
    concurrency: int = 4,
) -> int:
    """Fetch remote metadata and refresh the local images it references.

    Remote entries override matching local metadata keys; local-only entries
    are preserved. Returns the number of successfully updated images.
    """
    root = Path(build_dir).expanduser() if build_dir else default_build_dir()
    root.mkdir(parents=True, exist_ok=True)

    try:
        async with session.get(
            metadata_url, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as response:
            if response.status != 200:
                raise HSR_Error(
                    f"Build metadata request failed with HTTP {response.status}: {metadata_url}"
                )
            payload = await response.json(content_type=None)
    except HSR_Error:
        raise
    except Exception as exc:
        raise HSR_Error(f"Could not fetch build metadata: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise HSR_Error("Build metadata must be a JSON object")

    remote: dict[int, dict[str, str]] = {}
    for key, value in payload.items():
        record = _record_from_payload(root, key, value)
        if record is not None:
            remote[record.character_id] = {
                "char_name": record.char_name,
                "raw_url": record.raw_url,
                "git_url": record.git_url,
            }

    if not remote:
        raise HSR_Error("Build metadata contains no character entries")

    local = _read_metadata(root / "metadata.json")
    merged = {key: value for key, value in local.items() if isinstance(value, Mapping)}
    merged.update({str(character_id): value for character_id, value in remote.items()})
    _write_metadata(root / "metadata.json", merged)

    semaphore = asyncio.Semaphore(max(1, int(concurrency)))
    failures: list[str] = []

    async def download(character_id: int, record: Mapping[str, str]) -> bool:
        async with semaphore:
            try:
                async with session.get(
                    record["raw_url"], timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status != 200:
                        raise HSR_Error(f"HTTP {response.status}")
                    data = await response.read()
                with Image.open(BytesIO(data)) as image:
                    image.verify()
                target = root / f"{character_id}.png"
                temp = target.with_name(target.name + ".tmp")
                await asyncio.to_thread(temp.write_bytes, data)
                await asyncio.to_thread(temp.replace, target)
                return True
            except Exception as exc:
                failures.append(f"{character_id}: {exc}")
                return False

    results = await asyncio.gather(
        *(download(character_id, record) for character_id, record in remote.items())
    )
    if failures:
        raise HSR_Error("Failed to update build images: " + "; ".join(failures))
    return sum(1 for result in results if result)