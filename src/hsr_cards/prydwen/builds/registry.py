"""Local build registry: parse drafts, validate, and approve them.

There is intentionally no automatic approval. A build becomes a library asset
only after a human changes ``review.status`` through ``hsr-prydwen approve``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Iterable

from .models import BuildCardData, ReviewInfo, ReviewStatus
from .nanoka import NanokaIndex


def load_build(path: Path) -> BuildCardData:
    return BuildCardData.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_build(data: BuildCardData, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def validate_build(data: BuildCardData, nanoka: NanokaIndex) -> list[str]:
    """Return review blockers; structural validation never implies approval."""
    problems: list[str] = list(data.warnings)
    if not data.character.nanoka_id:
        problems.append("character has no Nanoka id")
    if data.character.drawcard is None:
        problems.append("character has no drawcard asset")
    if data.character.rarity is None or "Unknown" in (data.character.element, data.character.path):
        problems.append("character identity is incomplete")
    if not data.source_meta or not data.source_meta.html_sha256:
        problems.append("no cached source hash recorded")
    if not data.character.last_updated:
        problems.append("no website last-updated date recorded")
    for ref in _asset_refs(data):
        if nanoka.asset_file(ref) is None:
            problems.append(f"missing local asset: {ref.ref} -> {ref.relative_path}")
    if not data.light_cones:
        problems.append("no light cones parsed")
    for cone in data.light_cones:
        if cone.asset is None:
            problems.append(f"unresolved light cone asset: {cone.name}")
    if not data.relic_sets or not any(group.recommendations for group in data.relic_sets):
        problems.append("no relic sets parsed")
    for group in data.relic_sets:
        for relic in group.recommendations:
            if relic.asset is None:
                problems.append(f"unresolved relic asset: {relic.name}")
    if not data.main_stats:
        problems.append("no main stats parsed")
    for choice in data.main_stats:
        if len(choice.operators) != max(0, len(choice.values) - 1):
            problems.append(f"ambiguous main-stat operators: {choice.slot}")
    if not any(mode.variants for mode in data.teams) and not data.editorial_teams and not data.synergies:
        problems.append("no teams or synergies parsed")
    for mode in data.teams:
        for team in mode.variants:
            if len(team.characters) != 4:
                problems.append(f"usage team in {mode.mode} does not have four characters")
            if len(team.character_assets) != len(team.characters) or any(ref is None for ref in team.character_assets):
                problems.append(f"unresolved usage-team assets in {mode.mode}")
    for team in data.editorial_teams:
        if not team.slots:
            problems.append(f"editorial team has no preserved slot alternatives: {team.name}")
        if any(member.asset is None for member in team.members):
            problems.append(f"unresolved editorial-team assets: {team.name}")
    unique: dict[str, str] = {}
    for problem in problems:
        unique.setdefault(problem.casefold(), problem)
    return list(unique.values())


def _asset_refs(data: BuildCardData) -> Iterable:
    """Walk every nested asset, including stat/trace icons added to the schema."""
    from .models import AssetRef, StrictModel

    def walk(value):
        if isinstance(value, AssetRef):
            yield value
        elif isinstance(value, StrictModel):
            for field in type(value).model_fields:
                yield from walk(getattr(value, field))
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from walk(child)
        elif isinstance(value, dict):
            for child in value.values():
                yield from walk(child)

    seen: set[str] = set()
    for ref in walk(data):
        if ref.relative_path not in seen:
            seen.add(ref.relative_path)
            yield ref


def _validate_cached_source(data: BuildCardData, build_path: Path) -> None:
    """Bind an explicit approval to the exact cached text used by this parse."""
    meta = data.source_meta
    if meta is None or meta.raw_file is None:
        return
    filename = meta.raw_file
    windows_path = PureWindowsPath(filename)
    if (not filename or filename in {".", ".."} or "/" in filename or "\\" in filename
            or windows_path.drive or windows_path.name != filename or Path(filename).name != filename):
        raise ValueError("raw_file must be a plain filename inside the adjacent raw directory")
    raw_root = (Path(build_path).resolve().parent.parent / "raw").resolve()
    cached = (raw_root / filename).resolve()
    try:
        cached.relative_to(raw_root)
    except ValueError as exc:
        raise ValueError("raw_file resolves outside the adjacent raw directory") from exc
    if not cached.is_file():
        raise ValueError(f"cached source snapshot is missing: {filename}")
    # parse_html hashes its UTF-8 input text; read_text performs the same newline
    # normalization used by the CLI, including on Windows CRLF cache files.
    actual_hash = hashlib.sha256(cached.read_bytes()).hexdigest()
    if actual_hash != meta.html_sha256:
        raise ValueError("cached source snapshot has changed; reparse and review before approval")


def approve_build(path: Path, *, reviewer: str, note: str | None = None, nanoka: NanokaIndex) -> BuildCardData:
    if not reviewer.strip():
        raise ValueError("reviewer must be named explicitly")
    data = load_build(path)
    _validate_cached_source(data, path)
    problems = validate_build(data, nanoka)
    if problems:
        raise ValueError("build has validation blockers:\n- " + "\n- ".join(problems))
    data.review = ReviewInfo(
        status=ReviewStatus.APPROVED,
        reviewer=reviewer,
        reviewed_at=datetime.now(timezone.utc),
        note=note,
    )
    write_build(data, path)
    return data
