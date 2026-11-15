"""Caller-relative paths, atomic cache writes, and task coordination."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Iterable

from ..constants import DEFAULT_CACHE_DIR, GAME_MODE_ALIASES
from ..exceptions import NanokaCacheError


MANIFEST_NAME = "manifest.json"

def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(value).split(".") if part.isdigit())

def default_cache_root() -> Path:
    """The cache lives next to the caller's project root, not the package."""
    return Path.cwd() / DEFAULT_CACHE_DIR

async def gather_bounded(awaitables: Iterable[Any]) -> None:
    """Run awaitables in a task group so failures cancel siblings cleanly."""
    if hasattr(asyncio, "TaskGroup"):
        async with asyncio.TaskGroup() as group:
            for awaitable in awaitables:
                group.create_task(awaitable)
        return
    pending = [asyncio.ensure_future(item) for item in awaitables]
    try:
        await asyncio.gather(*pending)
    except BaseException:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise

def shutil_rmtree(path: Path) -> None:
    """Remove the supplied cache directory tree, ignoring filesystem deletion errors."""
    import shutil

    shutil.rmtree(path, ignore_errors=True)

def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Replace a file through a sibling temporary file, creating parent directories.

    Retry brief Windows sharing violations; persistent conflicts raise
    NanokaCacheError. The temporary file is removed after success or failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                # Windows can briefly hold the target open after a concurrent
                # read; retry the atomic swap instead of failing the fetch.
                if attempt == 4:
                    raise NanokaCacheError(f"Could not update cache file {path}: {exc}") from exc
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)

def atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace a file with UTF-8 text without a BOM.

    Parent creation, Windows sharing retries, and errors follow atomic_write_bytes.
    """
    atomic_write_bytes(path, text.encode("utf-8"))

def mode_key(value: str) -> str:
    """Resolve a case-insensitive canonical mode or MOC/PF/AS/AA alias.

    Spaces/hyphens/underscores are normalized. Unsupported names raise ValueError;
    this pure helper performs no IO and does not enable AA floor cards.
    """
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if key in GAME_MODE_ALIASES:
        return GAME_MODE_ALIASES[key]
    for alias, canonical in GAME_MODE_ALIASES.items():
        if alias.replace("_", " ") == key.replace("_", " "):
            return canonical
    raise ValueError(
        f"Unknown endgame mode {value!r}; use maze, maze_extra, maze_boss, or maze_peak"
    )
