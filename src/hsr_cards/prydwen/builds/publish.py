"""Publish approved PNGs and their metadata into the character-build assets."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ...builds import _filename, _read_metadata, _write_metadata, build_raw_url, build_tree_url
from .models import BuildCardData, ReviewStatus


def publish_build(data: BuildCardData, image: Path, report: Path, build_dir: Path) -> Path:
    if data.review.status != ReviewStatus.APPROVED:
        raise ValueError("Only approved builds can be published")
    if data.character.nanoka_id is None:
        raise ValueError("An approved build needs a character id")
    slug = _filename(data.character.slug)
    rendered = json.loads(report.read_text(encoding="utf-8"))
    detailed = not rendered["exclude_extra"]
    stem = slug + (".detailed" if detailed else "")
    folder = build_dir / slug
    folder.mkdir(parents=True, exist_ok=True)
    old = _read_metadata(folder / "metadata.json")
    source_hash = data.source_meta.html_sha256 if data.source_meta else None
    images = [item for item in old.get("images", [])
              if item["detailed"] != detailed and old.get("source_html_sha256") == source_hash]
    for index, filename in enumerate(rendered["outputs"]):
        source = image.parent / _filename(filename)
        name = stem + ("" if index == 0 else f".conditions-{index:02d}") + ".png"
        target = folder / name
        temporary = target.with_name(target.name + ".tmp")
        shutil.copyfile(source, temporary)
        temporary.replace(target)
        images.append({
            "filename": name, "detailed": detailed,
            "raw_url": build_raw_url(slug, name), "git_url": build_tree_url(slug, name),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "size": rendered["size"],
        })
    images.sort(key=lambda item: (item["detailed"], ".conditions-" in item["filename"], item["filename"]))
    # Remove only previously published files no longer present in this record.
    keep = {item["filename"] for item in images}
    for item in old.get("images", []):
        name = _filename(item["filename"])
        if name not in keep:
            (folder / name).unlink(missing_ok=True)
    metadata = {
        "schema_version": 1, "character_id": data.character.nanoka_id,
        "char_name": data.character.name, "slug": slug,
        "source": data.source, "source_html_sha256": source_hash,
        "website_last_updated": data.character.last_updated,
        "review": data.review.model_dump(mode="json"),
        "rendered_at": datetime.now(timezone.utc).isoformat(), "images": images,
    }
    _write_metadata(folder / "metadata.json", metadata)
    catalog = _read_metadata(build_dir / "metadata.json")
    catalog[str(data.character.nanoka_id)] = metadata
    _write_metadata(build_dir / "metadata.json", catalog)
    return folder / f"{stem}.png"
