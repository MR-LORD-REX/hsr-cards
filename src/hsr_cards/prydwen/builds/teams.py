"""Derive the cross-character teams.json index from approved builds.

The per-character JSON is canonical. This file is a denormalized lookup for
"who appears with whom", so it must never introduce a second identity source:
characters are keyed by Nanoka id whenever one resolves, with the slug only as
a last-resort key for an unresolved name.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import BuildCardData, ReviewStatus, TeamIndex
from .nanoka import NanokaIndex


def _character_key(identifier: int | None, fallback: str) -> str:
    return f"nanoka:{identifier}" if identifier is not None else f"unresolved:{fallback}"


def _entry(name: str, identifier: int | None, source: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "nanoka_id": identifier,
        "source": source,
        "teams": [],
        "synergies": [],
        "appears_in": [],
    }


def _add_character(
    characters: dict[str, dict[str, Any]],
    name: str,
    nanoka: NanokaIndex,
    *,
    source: str | None = None,
) -> tuple[str, int | None]:
    identifier, resolved_name = nanoka.match_character(name)
    key = _character_key(identifier, resolved_name)
    entry = characters.setdefault(key, _entry(resolved_name, identifier, source))
    if source:
        entry["source"] = source
    return key, identifier


def build_team_index(
    data_dir: Path,
    *,
    nanoka: NanokaIndex | None = None,
    include_drafts: bool = False,
) -> TeamIndex:
    """Collect approved builds into a stable character-keyed team index.

    Drafts are intentionally excluded by default: a generated team graph is a
    library asset, and only reviewed build JSON may feed library assets.
    """
    data_dir = Path(data_dir)
    nanoka = nanoka or NanokaIndex()
    characters: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    for path in sorted(data_dir.glob("*.json")):
        if path.name == "teams.json":
            continue
        try:
            data = BuildCardData.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            skipped.append({"path": path.name, "reason": str(exc).splitlines()[0]})
            continue
        if data.review.status != ReviewStatus.APPROVED and not include_drafts:
            skipped.append({"path": path.name, "reason": "draft"})
            continue
        owner_key = _character_key(data.character.nanoka_id, data.character.slug)
        owner = characters.setdefault(
            owner_key,
            _entry(data.character.name, data.character.nanoka_id, data.source),
        )
        owner["source"] = data.source
        owner["build_slug"] = data.character.slug
        owner["review_status"] = data.review.status.value
        owner["source_meta"] = data.source_meta.model_dump(mode="json") if data.source_meta else None

        for mode in data.teams:
            for variant in mode.variants:
                owner["teams"].append(
                    {
                        "mode": mode.mode,
                        "label": mode.label,
                        "phase": mode.phase,
                        "source_path": mode.source_path,
                        "source_file": mode.source_file,
                        "characters": list(variant.characters),
                        "character_slugs": list(variant.character_slugs),
                        "raw_metrics": variant.raw_metrics,
                        "rank": variant.rank,
                        "application_rate": variant.application_rate,
                        "performance": variant.performance,
                        "source": data.source,
                    }
                )
                for member_index, member in enumerate(variant.characters):
                    if member == data.character.name:
                        continue
                    asset_ref = (
                        variant.character_assets[member_index]
                        if member_index < len(variant.character_assets)
                        else None
                    )
                    member_id = nanoka.character_id(name=member)
                    member_key = _character_key(member_id, member)
                    target = characters.setdefault(member_key, _entry(member, member_id))
                    if asset_ref is not None:
                        target["icon"] = asset_ref.model_dump(mode="json")
                    target["appears_in"].append(
                        {
                            "character": data.character.name,
                            "slug": data.character.slug,
                            "nanoka_id": data.character.nanoka_id,
                            "mode": mode.mode,
                            "label": mode.label,
                        "phase": mode.phase,
                        "source_path": mode.source_path,
                        "source_file": mode.source_file,
                        }
                    )

        for team in data.editorial_teams:
            owner["synergies"].append(
                {
                    "kind": "editorial_team",
                    "name": team.name,
                    "members": [
                        {
                            "name": member.name,
                            "role": member.role,
                            "nanoka_id": nanoka.character_id(name=member.name),
                            "asset": member.asset.model_dump(mode="json") if member.asset else None,
                        }
                        for member in team.members
                    ],
                    "slots": [slot.model_dump(mode="json") for slot in team.slots],
                    "note": team.note,
                    "source": data.source,
                }
            )
            for member in team.members:
                if member.name == data.character.name:
                    continue
                member_id = nanoka.character_id(name=member.name)
                member_key = _character_key(member_id, member.name)
                target = characters.setdefault(member_key, _entry(member.name, member_id))
                if member.asset is not None:
                    target["icon"] = member.asset.model_dump(mode="json")
                target["appears_in"].append(
                    {
                        "character": data.character.name,
                        "slug": data.character.slug,
                        "nanoka_id": data.character.nanoka_id,
                        "mode": "editorial",
                        "label": team.name,
                    }
                )

        for synergy in data.synergies:
            owner["synergies"].append(
                {
                    "kind": "synergy",
                    "characters": list(synergy.characters),
                    "role": synergy.role,
                    "note": synergy.note,
                    "source": data.source,
                }
            )
            for index, member in enumerate(synergy.characters):
                if member == data.character.name:
                    continue
                member_id = nanoka.character_id(name=member)
                member_key = _character_key(member_id, member)
                target = characters.setdefault(member_key, _entry(member, member_id))
                asset_ref = (
                    synergy.character_assets[index]
                    if index < len(synergy.character_assets)
                    else None
                )
                if asset_ref is not None:
                    target["icon"] = asset_ref.model_dump(mode="json")
                target["appears_in"].append(
                    {
                        "character": data.character.name,
                        "slug": data.character.slug,
                        "nanoka_id": data.character.nanoka_id,
                        "mode": "synergy",
                        "label": None,
                    }
                )

    for entry in characters.values():
        # Deterministic order keeps regeneration diffs reviewable.
        entry["teams"].sort(key=lambda item: (item["mode"] or "", item["rank"] or 10**9))
        entry["appears_in"].sort(
            key=lambda item: (item["character"] or "", item["mode"] or "", item["label"] or "")
        )
    return TeamIndex(
        generated_at=datetime.now(timezone.utc),
        characters=dict(sorted(characters.items())),
        skipped=skipped,
    )