"""Stable filenames and explicit render-cache roots; importing performs no IO."""
from __future__ import annotations
import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
_HASH_WIDTH = 10


def safe_filename(value: str, *, limit: int = 72) -> str:
    """Return a readable, sanitized filename component with a stable length limit.

    Unsafe separators/whitespace become underscores; empty values become unknown.
    Overlong names retain a prefix plus a ten-character SHA-1 suffix. No IO occurs.
    """
    cleaned = re.sub(r"[^\w.-]+", "_", str(value).strip(), flags=re.UNICODE)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    if not cleaned:
        cleaned = "unknown"
    if len(cleaned) <= limit:
        return cleaned
    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:_HASH_WIDTH]
    return f"{cleaned[: limit - _HASH_WIDTH - 1].rstrip('._-')}_{digest}"


def comparison_key(versions: Sequence[str]) -> str:
    """Join sanitized build labels with -- in input order; preserve comparison direction without IO."""
    return "--".join(safe_filename(version, limit=24) for version in versions)


def default_rendered_cache_dir() -> Path:
    """Return .hsr_cards_rendered under the caller cwd without creating it."""
    return Path.cwd() / ".hsr_cards_rendered"
