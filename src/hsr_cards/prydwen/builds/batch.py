"""Render locally cached builds and record an explicit per-character review queue."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from ...utils.hsrfonts import WINDOWS_FONT_DIR, load_font

from .models import ReviewStatus
from .nanoka import NanokaIndex
from .registry import load_build, validate_build


def render_batch(paths: list[Path], output: Path, *, nanoka: NanokaIndex, allow_draft: bool = False, exclude_extra: bool = True, client=None) -> dict:
    from .render import render_card

    output.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Generated drafts require individual human source and image review before approval.",
        "cards": [], "skipped": [], "failed": [],
    }
    for path in paths:
        try:
            data = load_build(path)
            if data.review.status != ReviewStatus.APPROVED and not allow_draft:
                manifest['skipped'].append({"slug": data.character.slug, "reason": "draft"})
                continue
            problems = validate_build(data, nanoka)
            if data.review.status == ReviewStatus.APPROVED and problems:
                raise ValueError('Approved build no longer validates: ' + '; '.join(problems))
            destination = output / f'{path.stem}.png'
            if client is not None:
                destination = client.card(data=path, out=destination, allow_draft=allow_draft, exclude_extra=exclude_extra)
                report_path = client.work_dir / "reports" / f"{destination.stem}.render.json"
            else:
                destination = render_card(data, destination, nanoka=nanoka, exclude_extra=exclude_extra)
                report_path = destination.with_suffix('.render.json')
            report = json.loads(report_path.read_text('utf-8')) if report_path.is_file() else {}
            manifest['cards'].append({
                "slug": data.character.slug, "name": data.character.name,
                "image": str(destination.resolve()), "data": str(path.resolve()),
                "review_status": data.review.status.value,
                "website_last_updated": data.character.last_updated,
                "source_url": data.source,
                "source_html_sha256": data.source_meta.html_sha256 if data.source_meta else None,
                "validation_issues": problems,
                "render_report": str(report_path.resolve()) if report else None,
                "conditions_images": report.get("condition_sheets", sorted(p.name for p in output.glob(f'{destination.stem}.conditions-*.png'))),
            })
            print(f'rendered {data.character.slug} ({data.review.status.value})', flush=True)
        except Exception as exc:
            manifest['failed'].append({"file": path.name, "error": str(exc)})
            print(f'FAILED {path.name}: {exc}', flush=True)
    manifest['contact_sheets'] = _contact_sheets(output, manifest['cards'])
    (output / 'review-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def _contact_sheets(output: Path, cards: list[dict]) -> list[str]:
    """An index for locating cards; full-size PNGs are the review artifacts."""
    width, height = 480, 404
    font = load_font(22, (WINDOWS_FONT_DIR / "arial.ttf",))
    results = []
    for start in range(0, len(cards), 12):
        sheet = Image.new('RGB', (width * 3, height * 4), '#121321')
        draw = ImageDraw.Draw(sheet)
        for offset, entry in enumerate(cards[start:start+12]):
            x, y = (offset % 3) * width, (offset // 3) * height
            with Image.open(output / entry['image']) as image:
                image.thumbnail((width - 16, height - 54), Image.Resampling.LANCZOS)
                sheet.paste(image.convert('RGB'), (x + (width-image.width)//2, y + 4))
            label = f"{entry['slug']} | {entry['review_status']}"
            draw.text((x+12, y+height-39), label, font=font, fill='#F8F0E4')
        name = f'contact-sheet-{start//12+1:02d}.jpg'
        sheet.save(output / name, quality=92)
        results.append(name)
    return results