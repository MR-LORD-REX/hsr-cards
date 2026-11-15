"""Approved build images, stored per character with clean and detailed variants."""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import aiohttp
from PIL import Image

from .utils.errors import HSR_Error

BUILD_REPO = "MR-LORD-REX/hsr-cards"
BUILD_BRANCH = "main"
BUILD_ASSET_PATH = "src/hsr_cards/assets/char_builds"
BUILD_RAW_BASE = f"https://raw.githubusercontent.com/{BUILD_REPO}/{BUILD_BRANCH}/{BUILD_ASSET_PATH}"
BUILD_TREE_BASE = f"https://github.com/{BUILD_REPO}/tree/{BUILD_BRANCH}/{BUILD_ASSET_PATH}"
BUILD_METADATA_URL = f"{BUILD_RAW_BASE}/metadata.json"


def default_build_dir() -> Path:
    """Return the local approved-build directory without creating it.

    Source checkouts retain their existing assets/char_builds tree. Installed
    packages use .hsr_cards_builds under the caller's working directory so an
    update never needs to write generated images into site-packages.
    """
    package_root = Path(__file__).resolve().parent
    source_builds = package_root / "assets" / "char_builds"
    source_checkout = (
        package_root.parent.name == "src"
        and (package_root.parent.parent / "pyproject.toml").is_file()
    )
    if source_checkout and source_builds.is_dir():
        return source_builds
    return Path.cwd() / ".hsr_cards_builds"


def _filename(value: object) -> str:
    text = str(value)
    if not text or text in {".", ".."} or any(char in text for char in '/\\:'):
        raise ValueError(f"Expected a plain filename: {text!r}")
    return text


def build_raw_url(character: str, filename: str) -> str:
    return f"{BUILD_RAW_BASE}/{quote(_filename(character))}/{quote(_filename(filename))}"


def build_tree_url(character: str, filename: str) -> str:
    return f"{BUILD_TREE_BASE}/{quote(_filename(character))}/{quote(_filename(filename))}"


@dataclass(frozen=True)
class CharacterBuild:
    character_id: int
    char_name: str
    slug: str
    raw_url: str
    git_url: str
    path: Path
    detailed: bool = False

    def load(self) -> Image.Image:
        with Image.open(self.path) as image:
            return image.convert("RGB").copy()


def _normalise(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _matches_name(query: str, candidate: str) -> bool:
    needle, name = _normalise(query), _normalise(candidate)
    return bool(needle and name and (needle == name or needle in name.split()))


def _read_metadata(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _records(root: Path, payload: Mapping) -> list[CharacterBuild]:
    identifier = int(payload["character_id"])
    slug = _filename(payload["slug"])
    records = []
    for image in payload.get("images", []):
        filename = _filename(image["filename"])
        if not filename.endswith(".png"):
            raise ValueError("Build images must be PNG files")
        records.append(CharacterBuild(
            character_id=identifier, char_name=str(payload["char_name"]), slug=slug,
            raw_url=str(image.get("raw_url") or build_raw_url(slug, filename)),
            git_url=str(image.get("git_url") or build_tree_url(slug, filename)),
            path=root / slug / filename, detailed=bool(image["detailed"]),
        ))
    return records


def scan_builds(build_dir: str | Path | None = None) -> list[CharacterBuild]:
    """Read the root index and each character's metadata on every lookup."""
    root = Path(build_dir).expanduser() if build_dir is not None else default_build_dir()
    payloads = _read_metadata(root / "metadata.json")
    for path in sorted(root.glob("*/metadata.json")):
        payload = _read_metadata(path)
        if "character_id" in payload:
            payloads[str(payload["character_id"])] = payload
    records = []
    for payload in payloads.values():
        if isinstance(payload, Mapping):
            try:
                records.extend(_records(root, payload))
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(records, key=lambda r: (r.character_id, r.detailed, ".conditions-" in r.path.name, r.path.name))


def find_builds(
    identifier: int | str | None = None, *, name: str | None = None,
    search: str | None = None, build_dir: str | Path | None = None,
    detailed: bool = False,
) -> list[CharacterBuild]:
    records = [record for record in scan_builds(build_dir) if record.detailed == detailed]
    if identifier is not None and str(identifier).strip().isdigit():
        return [record for record in records if record.character_id == int(identifier)]
    for query in (identifier, name, search):
        if query is None:
            continue
        match = next((record for record in records if
                      _matches_name(str(query), record.char_name) or
                      _matches_name(str(query), record.slug)), None)
        if match:
            return [record for record in records if record.character_id == match.character_id]
    return []


def find_build(identifier=None, **kwargs) -> CharacterBuild | None:
    return next(iter(find_builds(identifier, **kwargs)), None)


def load_build_image(record: CharacterBuild | None) -> Image.Image | None:
    if record is None or not record.path.is_file():
        return None
    try:
        return record.load()
    except Exception as exc:
        raise HSR_Error(f"Could not read build image {record.path}: {exc}") from exc


def _write_metadata(path: Path, payload: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


async def update_build_assets(
    session: aiohttp.ClientSession, *, metadata_url: str = BUILD_METADATA_URL,
    build_dir: str | Path | None = None, timeout: float = 30.0, concurrency: int = 4,
) -> int:
    """Download every indexed variant and condition page, then publish metadata.

    With no build_dir, use the source checkout's approved cards or the installed
    package's caller-local .hsr_cards_builds directory. Missing directories are
    created during the update; no cards need to be bundled in the distribution.
    Local-only characters are preserved. A failed download leaves the previous
    metadata intact, so an incomplete update cannot advertise missing cards.
    """
    root = Path(build_dir).expanduser() if build_dir is not None else default_build_dir()
    request_timeout = aiohttp.ClientTimeout(total=timeout)
    try:
        async with session.get(metadata_url, timeout=request_timeout) as response:
            if response.status != 200:
                raise HSR_Error(f"Build metadata request failed with HTTP {response.status}")
            payload = await response.json(content_type=None)
        if not isinstance(payload, Mapping):
            raise ValueError("Build metadata must be a JSON object")
        remote = {}
        records = []
        for key, value in payload.items():
            if not str(key).isdigit() or not isinstance(value, Mapping):
                raise ValueError(f"Invalid character metadata: {key!r}")
            images = _records(root, value)
            if int(key) != int(value["character_id"]) or not images:
                raise ValueError(f"Invalid character images: {key!r}")
            remote[str(key)] = dict(value)
            records.extend(images)
    except HSR_Error:
        raise
    except Exception as exc:
        raise HSR_Error(f"Could not fetch build metadata: {exc}") from exc

    semaphore = asyncio.Semaphore(max(1, int(concurrency)))

    async def download(record: CharacterBuild) -> None:
        async with semaphore:
            async with session.get(record.raw_url, timeout=request_timeout) as response:
                if response.status != 200:
                    raise HSR_Error(f"{record.path.name}: HTTP {response.status}")
                data = await response.read()
            with Image.open(BytesIO(data)) as image:
                if image.format != "PNG":
                    raise ValueError(f"Not a PNG: {record.path.name}")
                image.verify()
            record.path.parent.mkdir(parents=True, exist_ok=True)
            temp = record.path.with_name(record.path.name + ".tmp")
            await asyncio.to_thread(temp.write_bytes, data)
            await asyncio.to_thread(temp.replace, record.path)

    results = await asyncio.gather(*(download(record) for record in records), return_exceptions=True)
    failures = [str(result) for result in results if isinstance(result, Exception)]
    if failures:
        raise HSR_Error("Failed to update build images: " + "; ".join(failures))
    merged = _read_metadata(root / "metadata.json")
    merged.update(remote)
    for value in remote.values():
        _write_metadata(root / _filename(value["slug"]) / "metadata.json", value)
    _write_metadata(root / "metadata.json", merged)
    return len(records)
