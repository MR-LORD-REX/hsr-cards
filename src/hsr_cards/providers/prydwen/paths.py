"""Paths for local Prydwen work; approved images live in the package assets."""
from pathlib import Path


def default_work_dir() -> Path:
    """Find an existing ancestor work tree, otherwise return the cwd default.

    Resolves paths only; directory creation belongs to explicit pipeline calls.
    """
    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        candidate = parent / ".hsr_prydwen"
        if candidate.is_dir():
            return candidate
    return cwd / ".hsr_prydwen"


def default_nanoka_cache() -> Path:
    """Resolve a local Nanoka cache without printing or creating directories."""
    root = default_work_dir().parent
    for candidate in (root / "hsr_cards" / ".nanoka_cache", root / ".nanoka_cache"):
        if candidate.is_dir():
            return candidate
    return default_work_dir() / "nanoka"
