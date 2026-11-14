"""Exercise caching, explicit refresh and partial failures without a network."""
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from hsr_cards.prydwen.builds.fetch import FetchConfig, PrydwenFetcher, valid_html
from hsr_cards.prydwen.builds.roster import RosterEntry

HTML = '<html><head><title>Acheron Best Build Guide</title></head><body><div class="character-top"><h1>Acheron</h1></div><div class="content-header">Introduction</div></body></html>'
ENTRY = RosterEntry('acheron', 'Acheron', 'https://www.prydwen.gg/star-rail/characters/acheron')


def response(html=HTML, status=200):
    result = Mock()
    result.content = html.encode('utf-8')
    result.status_code = status
    result.headers = {'Last-Modified': 'server timestamp'}
    result.raise_for_status.return_value = None
    return result


def test_cache_skips_network_and_preserves_snapshot(tmp_path):
    async def run():
        async with PrydwenFetcher(FetchConfig(tmp_path)) as fetcher:
            fetcher._session_get = Mock(return_value=response())
            path = await fetcher.character(ENTRY)
            first_meta = path.with_suffix('.meta.json').read_bytes()
            assert await fetcher.character(ENTRY) == path
            assert fetcher._session_get.call_count == 1
            assert first_meta == path.with_suffix('.meta.json').read_bytes()
            assert fetcher.cached == 1
            assert fetcher.downloaded == 1
            metadata = json.loads(first_meta)
            assert len(metadata['html_sha256']) == 64
            assert metadata['http_last_modified'] == 'server timestamp'
            assert path.read_text('utf-8') == HTML
    asyncio.run(run())


def test_refresh_failure_preserves_previous_good_page(tmp_path):
    async def run():
        path = tmp_path / 'acheron.html'
        path.write_text(HTML, encoding='utf-8')
        async with PrydwenFetcher(FetchConfig(tmp_path, refresh=True, retries=0)) as fetcher:
            fetcher._session_get = Mock(return_value=response('<title>Just a moment...</title>'))
            paths = await fetcher.all([ENTRY])
            assert paths == []
            assert path.read_text('utf-8') == HTML
            assert json.loads((tmp_path / 'manifest.json').read_text('utf8'))['failures'][0]['slug'] == ENTRY.slug
    asyncio.run(run())


def test_batch_has_deterministic_order_and_keeps_other_successes(tmp_path):
    async def run():
        entries = [ENTRY, RosterEntry('cyrene', 'Cyrene', 'https://www.prydwen.gg/star-rail/characters/cyrene')]
        async with PrydwenFetcher(FetchConfig(tmp_path, retries=0)) as fetcher:
            fetcher._session_get = Mock(side_effect=[response(), RuntimeError('offline')])
            paths = await fetcher.all(entries, concurrency=1)
            assert [p.stem for p in paths] == ['acheron']
            manifest = json.loads((tmp_path / 'manifest.json').read_text('utf8'))
            assert (manifest['expected'], manifest['available']) == (2, 1)
            assert manifest['failures'][0]['slug'] == 'cyrene'
    asyncio.run(run())


@pytest.mark.parametrize('html', ['<title>404 Not Found</title>', '<title>Just a moment...</title>', '<h1>Empty shell</h1>'])
def test_rejects_noncharacter_pages(html):
    assert not valid_html(html)


def test_cache_works_while_completely_offline(tmp_path):
    async def run():
        (tmp_path / 'acheron.html').write_text(HTML, encoding='utf-8')
        async with PrydwenFetcher(FetchConfig(tmp_path)) as fetcher:
            fetcher._session_get = Mock(side_effect=AssertionError('Network must never be called'))
            assert await fetcher.character(ENTRY) == tmp_path / 'acheron.html'
            assert fetcher._session_get.call_count == 0
    asyncio.run(run())

def test_raw_response_bytes_and_hash_keep_original_line_endings(tmp_path):
    async def run():
        html = HTML + '\r\n<!--original CRLF-->\n'
        async with PrydwenFetcher(FetchConfig(tmp_path)) as fetcher:
            fetcher._session_get = Mock(return_value=response(html))
            path = await fetcher.character(ENTRY)
            assert path.read_bytes() == html.encode('utf-8')
            import hashlib
            metadata = json.loads(path.with_suffix('.meta.json').read_text('utf8'))
            assert metadata['html_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
            assert await fetcher.character(ENTRY) == path
            assert fetcher._session_get.call_count == 1
    asyncio.run(run())


def test_modified_cache_is_repaired_instead_of_trusted(tmp_path):
    async def run():
        async with PrydwenFetcher(FetchConfig(tmp_path)) as fetcher:
            fetcher._session_get = Mock(return_value=response())
            path = await fetcher.character(ENTRY)
            path.write_bytes((HTML + '<!--modified-->').encode('utf8'))
            await fetcher.character(ENTRY)
            assert fetcher._session_get.call_count == 2
            assert path.read_bytes() == HTML.encode('utf8')
    asyncio.run(run())