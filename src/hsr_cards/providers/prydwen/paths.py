"""Paths for local Prydwen work; approved images live in the package assets."""
import os
from pathlib import Path
import shutil
import sys


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


def discover_chrome() -> Path | None:
    """Find an installed Chrome/Chromium at call time, without launching a browser.

    Return None when no installation is found so Playwright can use its managed
    Chromium. PATH is checked before conventional locations on each platform.
    """
    for command in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "chrome.exe"):
        executable = shutil.which(command)
        if executable:
            return Path(executable)

    candidates = []
    if sys.platform == "win32":
        roots = [os.environ.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        roots.extend(("C:/Program Files", "C:/Program Files (x86)"))
        candidates.extend(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe" for root in roots if root)
    elif sys.platform == "darwin":
        candidates.extend((
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ))
    else:
        candidates.extend(Path(path) for path in (
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium", "/usr/bin/chromium-browser", "/opt/google/chrome/chrome",
        ))
    return next((path for path in candidates if path.is_file()), None)
