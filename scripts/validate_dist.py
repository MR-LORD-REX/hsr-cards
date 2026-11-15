"""Check release archives stay below PyPI's size limit and omit generated builds."""
from __future__ import annotations

import argparse
from pathlib import Path
import tarfile
import zipfile


MAX_FILE_SIZE = 100_000_000
RUNTIME_FILES = (
    "hsr_cards/__init__.py",
    "hsr_cards/builds.py",
    "hsr_cards/clients/main.py",
    "hsr_cards/assets/fonts/optimized_global_web.woff2",
    "hsr_cards/assets/backgrounds/ANO/main_bg.png",
    "hsr_cards/assets/backgrounds/AS/main_bg.png",
    "hsr_cards/assets/backgrounds/MOC/main_bg.png",
    "hsr_cards/assets/backgrounds/PF/main_bg.png",
    "hsr_cards/assets/team/team_bg.png",
)


def archive_files(path: Path) -> set[str]:
    """Read wheel/sdist member names without extracting or importing package code."""
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            return {name for name in archive.namelist() if not name.endswith("/")}
    with tarfile.open(path, "r:gz") as archive:
        return {member.name for member in archive.getmembers() if member.isfile()}


def generated_build(name: str) -> bool:
    """Identify generated build trees, including repository and downloaded copies."""
    parts = name.replace("\\", "/").split("/")
    return ".hsr_cards_builds" in parts or any(
        left == "assets" and right == "char_builds"
        for left, right in zip(parts, parts[1:])
    )


def validate_dist(directory: Path, *, max_size: int = MAX_FILE_SIZE) -> list[str]:
    """Check one wheel and one sdist for size, runtime files and generated assets.

    Return actionable error messages; an empty list means the files are ready for
    upload. max_size is a per-file byte limit, defaulting to a conservative 100 MB.
    No files are modified and no network access is required.
    """
    issues = []
    wheels = sorted(directory.glob("*.whl"))
    sources = sorted(directory.glob("*.tar.gz"))
    for kind, files in (("wheel", wheels), ("sdist", sources)):
        if len(files) != 1:
            issues.append(f"Expected one {kind} in {directory}, found {len(files)}")
    for path in wheels + sources:
        size = path.stat().st_size
        if size >= max_size:
            issues.append(f"{path.name}: {size / 1_000_000:.2f} MB exceeds the {max_size / 1_000_000:g} MB limit")
        try:
            files = archive_files(path)
        except (OSError, ValueError, zipfile.BadZipFile, tarfile.TarError) as error:
            issues.append(f"{path.name}: unreadable archive ({error})")
            continue
        generated = sorted(name for name in files if generated_build(name))
        if generated:
            issues.append(f"{path.name}: contains {len(generated)} generated build files (first: {generated[0]})")
        if path.name.endswith(".whl"):
            expected = set(RUNTIME_FILES)
        else:
            roots = {name.split("/", 1)[0] for name in files}
            if len(roots) != 1:
                issues.append(f"{path.name}: expected one sdist root directory")
                continue
            prefix = next(iter(roots)) + "/"
            expected = {prefix + "src/" + name for name in RUNTIME_FILES}
            expected.update(prefix + name for name in ("README.md", "LICENSE", "pyproject.toml", "MANIFEST.in"))
        for missing in sorted(expected - files):
            issues.append(f"{path.name}: missing runtime/source file {missing}")
    return issues


def main() -> None:
    """Validate dist/ or a supplied archive directory and print artifact sizes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    issues = validate_dist(args.directory)
    if issues:
        parser.exit(1, "Distribution validation failed:\n" + "\n".join(f"- {issue}" for issue in issues) + "\n")
    for path in sorted(args.directory.iterdir()):
        if path.name.endswith((".whl", ".tar.gz")):
            print(f"Verified {path.name}: {path.stat().st_size / 1_000_000:.2f} MB")


if __name__ == "__main__":
    main()
