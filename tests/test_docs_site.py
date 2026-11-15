"""Portable regressions for Markdown bundles, public links, and showcase assets."""
import json
from pathlib import Path
import struct

import pytest

from scripts.build_docs import build, load_docs, render_bundle
from scripts.validate_docs import api_coverage, check_link, heading_ids, python_examples, showcase_issues, validate


def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.3.4"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "getting-started").mkdir(parents=True)
    (docs / "data").mkdir()
    (docs / "assets").mkdir()
    (docs / "readme.md").write_text('# HSR Cards\n\n[Quickstart](getting-started/quickstart.md#first-card)\n', encoding="utf-8")
    (docs / "showcase.md").write_text('# Showcase\n\n![Example](assets/card.webp)\n', encoding="utf-8")
    (docs / "getting-started" / "quickstart.md").write_text('# Quickstart\n\n## First card\n\nExample.\n', encoding="utf-8")
    (docs / "assets" / "card.webp").write_bytes(b"example preview")
    cards = tmp_path / "Cards"
    cards.mkdir()
    # The validator reads the IHDR header; the real render tests verify full PNG decoding.
    (cards / "showcase-card.png").write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1080, 1440))
    metadata = {"items": [{"id": "character-info", "method": "get_character_info", "title": "Character info",
                            "image": "assets/card.webp", "original": "https://raw.githubusercontent.com/example/repo/main/Cards/showcase-card.png",
                            "source": "Cached data", "description": "A rendered character card", "width": 1080, "height": 1440}], "unavailable": []}
    (docs / "data" / "showcase.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_bundle_uses_publishable_posix_routes_and_authoritative_project_version(tmp_path):
    root = project(tmp_path)
    catalog = load_docs(root)
    assert catalog["version"] == "2.3.4"
    assert [page["id"] for page in catalog["pages"]] == ["readme", "getting-started/quickstart", "showcase"]
    assert catalog["pages"][1]["section"] == "Getting started"
    assert catalog["pages"][1]["content"].startswith("# Quickstart")
    assert catalog["showcase"]["items"][0]["image"] == "assets/card.webp"


def test_bundle_is_deterministic_and_staleness_detects_changed_markdown_without_writing(tmp_path):
    root = project(tmp_path)
    destination = build(root)
    original = destination.read_bytes()
    build(root, check=True)
    (root / "docs" / "readme.md").write_text("# Updated title\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        build(root, check=True)
    assert destination.read_bytes() == original
    build(root)
    assert destination.read_bytes() != original


def test_bundle_escapes_script_boundaries_and_unicode_line_separators():
    catalog = {"pages": [{"content": '</script>\u2028\u2029&"'}]}
    rendered = render_bundle(catalog)
    assert "</script>" not in rendered
    assert "\\u2028" in rendered and "\\u2029" in rendered
    value = rendered.split("window.HSR_DOCS = ", 1)[1].removesuffix(";\n")
    assert json.loads(value) == catalog


def test_link_validation_checks_page_anchors_and_rejects_unpublished_siblings(tmp_path):
    root = project(tmp_path)
    source = root / "docs" / "readme.md"
    ids = {page["id"] for page in load_docs(root)["pages"]}
    assert check_link(root, source, "getting-started/quickstart.md#first-card", ids) is None
    assert "unknown Markdown anchor" in check_link(root, source, "getting-started/quickstart.md#missing", ids)
    assert "escapes" in check_link(root, source, "../Cards/showcase-card.png", ids)
    assert "does not exist" in check_link(root, source, "guides/missing.md", ids)


def test_duplicate_headings_have_stable_github_fragments_and_code_fences_are_ignored():
    markdown = '# Reference\n## `save()`\n## `save()`\n```md\n## Fake\n```\n<a id="stable-save"></a>\n'
    assert heading_ids(markdown) == {"reference", "save", "save-1", "stable-save"}


def test_showcase_requires_deployable_previews_and_canonical_png_dimensions(tmp_path):
    root = project(tmp_path)
    metadata = load_docs(root)["showcase"]
    assert showcase_issues(root, metadata) == []
    metadata["items"][0]["width"] = 999
    assert any("dimensions differ" in issue for issue in showcase_issues(root, metadata))
    metadata["items"][0]["image"] = "../Cards/showcase-card.png"
    assert any("publishable docs asset" in issue for issue in showcase_issues(root, metadata))


def test_validator_accepts_complete_offline_site_and_fails_missing_assets(tmp_path):
    root = project(tmp_path)
    docs = root / "docs"
    (docs / "index.html").write_text('<link rel="stylesheet" href="style.css"><script src="data/content.js"></script><script src="app.js"></script><a href="index.html#/showcase">Gallery</a>', encoding="utf-8")
    (docs / "style.css").write_text("body { color: black; }", encoding="utf-8")
    (docs / "app.js").write_text("window.documentationLoaded = true;", encoding="utf-8")
    build(root)
    assert validate(root, coverage=False) == []
    (docs / "app.js").unlink()
    assert any("app.js" in issue for issue in validate(root, coverage=False))


def test_unknown_site_routes_are_reported_without_rejecting_relative_html_links(tmp_path):
    root = project(tmp_path)
    source = root / "docs" / "index.html"
    source.write_text("<!doctype html>", encoding="utf-8")
    ids = {page["id"] for page in load_docs(root)["pages"]}
    assert check_link(root, source, "index.html#/showcase", ids) is None
    assert "unknown site route" in check_link(root, source, "index.html#/missing", ids)
    assert check_link(root, source, "index.html#/getting-started/quickstart#first-card", ids) is None
    assert "unknown site heading" in check_link(root, source, "index.html#/getting-started/quickstart#missing", ids)


def test_existing_private_runtime_files_are_not_accepted_as_public_links(tmp_path):
    root = project(tmp_path)
    private = root / "docs" / ".nanoka_cache"
    private.mkdir()
    (private / "payload.json").write_text("{}", encoding="utf-8")
    assert "private" in check_link(root, root / "docs" / "readme.md", ".nanoka_cache/payload.json", {"readme"})


def test_reference_coverage_detects_undocumented_public_members_and_includes_split_nanoka_pages(tmp_path):
    root = project(tmp_path)
    clients = root / "src" / "hsr_cards" / "clients"
    queries = root / "src" / "hsr_cards" / "providers" / "nanoka"
    clients.mkdir(parents=True)
    queries.mkdir(parents=True)
    (clients / "main.py").write_text('class HonkaiStarrail:\n    def close(self): pass\n    @property\n    def api(self): pass\n    def _private(self): pass\n', encoding="utf-8")
    (queries / "characters.py").write_text('class CharactersQueries:\n    def list_characters(self): pass\n', encoding="utf-8")
    reference = root / "docs" / "api"
    (reference / "nanoka").mkdir(parents=True)
    (reference / "main-client.md").write_text('# Main client\n## close()\n', encoding="utf-8")
    (reference / "nanoka" / "characters.md").write_text('# Characters\n## list_characters()\n', encoding="utf-8")
    issues = api_coverage(root)
    assert issues == ["API main-client: missing method/property heading for api"]
    (reference / "main-client.md").write_text('# Main client\n## close()\n## api\n', encoding="utf-8")
    assert api_coverage(root) == []


def test_python_examples_allow_notebook_await_and_report_syntax_errors(tmp_path):
    root = project(tmp_path)
    page = root / "docs" / "getting-started" / "quickstart.md"
    page.write_text('# Quickstart\n## First card\n```python\nawait client.get_character_info(1507)\n```\n', encoding="utf-8")
    build(root)
    assert not any("invalid Python example" in issue for issue in validate(root, coverage=False, require_site=False))
    page.write_text('# Quickstart\n## First card\n```python\nif True\n    pass\n```\n', encoding="utf-8")
    build(root)
    assert any("invalid Python example" in issue for issue in validate(root, coverage=False, require_site=False))
    assert python_examples('```bash\necho hello\n```\n```py\nvalue = 1\n```') == [(5, "value = 1")]
