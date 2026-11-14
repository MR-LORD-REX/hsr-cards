"""Paths for local Prydwen work; approved images live in the package assets."""
from pathlib import Path


def default_work_dir() -> Path:
    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        candidate = parent / ".hsr_prydwen"
        if candidate.is_dir():
            print(f"[*] Using work dir: {candidate}")
            return candidate
        print(f"[*] Creating work dir: {candidate}")
    return cwd / ".hsr_prydwen"


def default_nanoka_cache() -> Path:
    root = default_work_dir().parent
    for candidate in (root / "hsr_cards" / ".nanoka_cache", root / ".nanoka_cache"):
        if candidate.is_dir():
            print(f"[*] Using Nanoka cache dir: {candidate}")
            return candidate
        print(f"[*] Creating Nanoka cache dir: {candidate}")
    return default_work_dir() / "nanoka"
