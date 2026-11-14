"""A batch preview never becomes a reviewed/publishable card implicitly."""
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import Mock

from PIL import Image

from hsr_cards.prydwen.builds.batch import render_batch
from hsr_cards.prydwen.builds.models import BuildCardData, CharacterIdentity, ReviewInfo, ReviewStatus


def build(path: Path, status=ReviewStatus.DRAFT):
    data = BuildCardData(
        generated_at=datetime.now(timezone.utc), source='https://www.prydwen.gg/star-rail/characters/test',
        character=CharacterIdentity(name='Test', slug='test', rarity=5, element='Ice', path='Erudition', source_url='https://www.prydwen.gg/star-rail/characters/test'),
        review=ReviewInfo(status=status),
    )
    path.write_text(data.model_dump_json(), encoding='utf-8')
    return data


def test_drafts_skipped_by_default_without_invoking_renderer(tmp_path, monkeypatch):
    source = tmp_path / 'test.json'
    build(source)
    renderer = Mock(side_effect=AssertionError('must skip'))
    monkeypatch.setattr('hsr_cards.prydwen.builds.render.render_card', renderer)
    result = render_batch([source], tmp_path / 'out', nanoka=Mock())
    assert result['cards'] == []
    assert result['skipped'] == [{'slug': 'test', 'reason': 'draft'}]
    renderer.assert_not_called()


def test_explicit_preview_records_problems_and_keeps_review_draft(tmp_path, monkeypatch):
    source = tmp_path / 'test.json'
    build(source)
    def render(data, destination, **kwargs):
        Image.new('RGB', (192, 144)).save(destination)
        destination.with_suffix('.render.json').write_text('{}', encoding='utf-8')
        destination.with_name('test.conditions-01.png').write_bytes(b'fake-condition-page')
        return destination
    monkeypatch.setattr('hsr_cards.prydwen.builds.render.render_card', render)
    result = render_batch([source], tmp_path / 'out', nanoka=Mock(), allow_draft=True)
    entry = result['cards'][0]
    assert entry['review_status'] == 'draft'
    assert entry['validation_issues']
    assert entry['conditions_images'] == ['test.conditions-01.png']
    assert json.loads(source.read_text('utf-8'))['review']['status'] == 'draft'
    assert result['contact_sheets'] == ['contact-sheet-01.jpg']


def test_invalid_approved_build_is_blocked(tmp_path, monkeypatch):
    source = tmp_path / 'test.json'
    build(source, ReviewStatus.APPROVED)
    renderer = Mock()
    monkeypatch.setattr('hsr_cards.prydwen.builds.render.render_card', renderer)
    result = render_batch([source], tmp_path / 'out', nanoka=Mock())
    assert len(result['failed']) == 1
    assert 'no light cones' in result['failed'][0]['error']
    renderer.assert_not_called()