"""Validate public documentation links, assets, API coverage, and site bundles."""
from __future__ import annotations

import argparse
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
from urllib.parse import unquote, urlsplit

if __package__:
    from .build_docs import ROOT, build, load_docs, markdown_files
else:
    from build_docs import ROOT, build, load_docs, markdown_files


def heading_slug(text: str) -> str:
    """Return a GitHub-compatible heading fragment for authored Markdown."""
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").lower().strip()
    text = re.sub(r"[^\w\-\s]", "", text, flags=re.UNICODE)
    return re.sub(r"\s", "-", text)


def without_fences(markdown: str) -> str:
    """Ignore code blocks when checking headings and Markdown link destinations."""
    output = []
    fence = None
    for line in markdown.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            if fence is None:
                fence = match.group(1)[0]
            elif match.group(1)[0] == fence:
                fence = None
            output.append("")
        elif fence is None:
            output.append(line)
    return "\n".join(output)


def heading_ids(markdown: str) -> set[str]:
    """Collect heading IDs, including the suffixes used for duplicate headings."""
    counts: dict[str, int] = {}
    identifiers = set()
    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", without_fences(markdown), re.M):
        slug = heading_slug(match.group(1))
        suffix = counts.get(slug, 0)
        identifiers.add(f"{slug}-{suffix}" if suffix else slug)
        counts[slug] = suffix + 1
    # Authors may deliberately expose stable anchors for long API signatures.
    identifiers.update(re.findall(r'<(?:a|span)\s+[^>]*id=[\"\']([^\"\']+)[\"\']', markdown))
    return identifiers


def python_examples(markdown: str) -> list[tuple[int, str]]:
    """Return fenced Python snippets and their first source line numbers."""
    examples = []
    marker = None
    lines: list[str] = []
    start = 0
    language = ""
    for number, line in enumerate(markdown.splitlines(), start=1):
        fence = re.match(r"^\s*(`{3,}|~{3,})([^\s`]*)", line)
        if marker is None and fence:
            marker = fence.group(1)
            language = fence.group(2).lower()
            start = number + 1
            lines = []
        elif marker is not None and re.match(rf"^\s*{re.escape(marker[0])}{{{len(marker)},}}\s*$", line):
            if language in {"python", "py"}:
                examples.append((start, "\n".join(lines)))
            marker = None
        elif marker is not None:
            lines.append(line)
    return examples


def inside(path: Path, directory: Path) -> bool:
    """Check a resolved local destination stays in the publishable docs tree."""
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def check_link(root: Path, source: Path, destination: str, page_ids: set[str]) -> str | None:
    """Validate one relative Markdown/site link without fetching remote resources."""
    target = destination.strip()
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        target = re.split(r'\s+[\"\']', target, maxsplit=1)[0]
    parsed = urlsplit(target)
    if parsed.scheme in {"https", "http", "mailto", "tel"}:
        return None
    if parsed.scheme or target.startswith(("/", "\\")):
        return "must use a public relative path or HTTPS URL"
    private_parts = {".env", ".git", ".nanoka_cache", ".hsr_cards_rendered", ".hsr_prydwen"}
    if set(Path(unquote(parsed.path)).parts) & private_parts:
        return "refers to a private configuration or runtime cache"
    docs = root / "docs"
    resolved = source if not parsed.path else source.parent / unquote(parsed.path)
    if not inside(resolved, docs):
        return "escapes the docs publishing directory"
    if not resolved.is_file():
        return "destination does not exist"
    fragment = unquote(parsed.fragment)
    if resolved.suffix.lower() == ".md" and fragment:
        if fragment not in heading_ids(resolved.read_text(encoding="utf-8-sig")):
            return f"unknown Markdown anchor #{fragment}"
    if resolved.suffix.lower() == ".html" and fragment.startswith("/"):
        route = fragment[1:].split("#", 1)[0].split("?", 1)[0]
        if route not in page_ids:
            return f"unknown site route /{route}"
        if "#" in fragment:
            anchor = fragment.split("#", 1)[1]
            page = docs / f"{route}.md"
            if page.is_file() and anchor not in heading_ids(page.read_text(encoding="utf-8-sig")):
                return f"unknown site heading #{anchor}"
    return None


class SiteAssets(HTMLParser):
    """Collect declared script, stylesheet, image, and navigation destinations."""

    def __init__(self) -> None:
        super().__init__()
        self.assets: list[tuple[str, str]] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record assets and href destinations from a parsed HTML start tag."""
        attributes = dict(attrs)
        source = attributes.get("src")
        href = attributes.get("href")
        if tag in {"script", "img", "source"} and source:
            self.assets.append((tag, source))
        if tag == "link" and href:
            self.assets.append((tag, href))
        if tag == "a" and href:
            self.links.append(href)


def public_members(path: Path, classname: str) -> set[str]:
    """Read class method/property names with AST, without importing provider code."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    result = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == classname:
            result.update(child.name for child in node.body
                          if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"))
    return result


def api_coverage(root: Path) -> list[str]:
    """Require a reference heading for each public client/API method or property."""
    package = root / "src" / "hsr_cards"
    docs = root / "docs" / "api"
    specs = {
        "main-client": [("clients/main.py", "HonkaiStarrail"), ("clients/player_cards.py", "PlayerCardMethods"), ("clients/nanoka_cards.py", "NanokaCardMethods")],
        "nanoka-client": [("clients/nanoka.py", "NanokaClient"), *[(f"providers/nanoka/{module}.py", classname) for module, classname in (
            ("characters", "CharactersQueries"), ("equipment", "EquipmentQueries"), ("monsters", "MonstersQueries"),
            ("schedules", "SchedulesQueries"), ("items", "ItemsQueries"), ("assets", "AssetsQueries"))]],
        "prydwen-client": [("clients/prydwen.py", "PrydwenClient")],
        "hoyolab-client": [("clients/hoyolab.py", "HoYoLABClient")],
        "provider-apis": [("providers/hoyolab/api.py", "BaseAPI"), ("providers/nanoka/api.py", "NanokaAPIClient"), ("providers/prydwen/api.py", "PrydwenAPIClient")],
    }
    issues = []
    for page, classes in specs.items():
        if not any((package / relative).is_file() for relative, _ in classes):
            continue
        paths = [docs / f"{page}.md", *(docs / page).rglob("*.md")]
        if page == "nanoka-client":
            paths.extend((docs / "nanoka").rglob("*.md"))
        contents = "\n".join(path.read_text(encoding="utf-8-sig") for path in paths if path.is_file())
        headers = "\n".join(re.findall(r"^#{1,6}\s+(.+)$", without_fences(contents), re.M)).replace("`", "")
        members = set()
        for relative, classname in classes:
            path = package / relative
            if path.is_file():
                members.update(public_members(path, classname))
        for member in sorted(members):
            if not re.search(rf"(?<![\w]){re.escape(member)}(?![\w])", headers):
                issues.append(f"API {page}: missing method/property heading for {member}")
    return issues


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read canonical PNG dimensions without requiring a third-party image package."""
    with path.open("rb") as file:
        header = file.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("invalid PNG header")
    return struct.unpack(">II", header[16:24])


def showcase_issues(root: Path, metadata: dict) -> list[str]:
    """Check demo IDs, deployable previews, canonical PNG paths, and dimensions."""
    issues = []
    used = set()
    for item in metadata.get("items", []):
        identifier = item.get("id")
        if not identifier or identifier in used:
            issues.append(f"Showcase: missing or duplicate ID {identifier!r}")
        used.add(identifier)
        for field in ("method", "title", "image", "original", "source", "description"):
            if not item.get(field):
                issues.append(f"Showcase {identifier}: missing {field}")
        preview = root / "docs" / str(item.get("image", ""))
        if not inside(preview, root / "docs") or not preview.is_file():
            issues.append(f"Showcase {identifier}: preview is not a publishable docs asset")
        parts = Path(unquote(urlsplit(str(item.get("original", ""))).path)).parts
        if "Cards" not in parts:
            issues.append(f"Showcase {identifier}: original does not refer to Cards/")
            continue
        original = root.joinpath(*parts[parts.index("Cards"):])
        if not inside(original, root / "Cards") or not original.is_file():
            issues.append(f"Showcase {identifier}: canonical PNG does not exist")
            continue
        try:
            width, height = png_dimensions(original)
            if (item.get("width"), item.get("height")) != (width, height):
                issues.append(f"Showcase {identifier}: dimensions differ from canonical PNG ({width}x{height})")
        except (OSError, ValueError) as error:
            issues.append(f"Showcase {identifier}: {error}")
    return issues


def validate(root: Path = ROOT, *, coverage: bool = True, require_site: bool = True) -> list[str]:
    """Return publish-blocking documentation issues; never modify source files."""
    docs = root / "docs"
    try:
        catalog = load_docs(root)
    except (OSError, ValueError) as error:
        return [str(error)]
    page_ids = {page["id"] for page in catalog["pages"]}
    issues = []
    for required in ("readme", "showcase"):
        if required not in page_ids:
            issues.append(f"Missing public {required}.md page")
    for path in markdown_files(docs):
        source = path.read_text(encoding="utf-8-sig")
        markdown = without_fences(source)
        for match in re.finditer(r"!?\[[^\]]*\]\((<[^>]+>|[^\n]*?)\)", markdown):
            destination = match.group(1)
            error = check_link(root, path, destination, page_ids)
            if error:
                issues.append(f"{path.relative_to(root).as_posix()}: {destination}: {error}")
        for start, example in python_examples(source):
            try:
                compile(example, path.name, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
            except SyntaxError as error:
                issues.append(f"{path.relative_to(root).as_posix()}:{start + (error.lineno or 1) - 1}: invalid Python example: {error.msg}")
    index = docs / "index.html"
    if require_site and not index.is_file():
        issues.append("Missing docs/index.html")
    if index.is_file():
        parser = SiteAssets()
        parser.feed(index.read_text(encoding="utf-8-sig"))
        for kind, destination in parser.assets:
            if urlsplit(destination).scheme:
                issues.append(f"docs/index.html: {kind} asset relies on a CDN: {destination}")
            else:
                error = check_link(root, index, destination, page_ids)
                if error:
                    issues.append(f"docs/index.html: {destination}: {error}")
        for destination in parser.links:
            error = check_link(root, index, destination, page_ids)
            if error:
                issues.append(f"docs/index.html: {destination}: {error}")
    try:
        build(root, check=True)
    except (OSError, ValueError) as error:
        issues.append(str(error))
    issues.extend(showcase_issues(root, catalog["showcase"]))
    if not catalog["showcase"].get("items"):
        issues.append("Showcase has no rendered outputs")
    if coverage:
        issues.extend(api_coverage(root))
    return issues


def main() -> None:
    """Validate the publishable site; print issues and exit nonzero on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-api-coverage", action="store_true", help="validate content/assets without comparing runtime API sources")
    args = parser.parse_args()
    issues = validate(coverage=not args.skip_api_coverage)
    if issues:
        print("Documentation validation failed:")
        for issue in issues:
            print(f"- {issue}")
        parser.exit(1)
    catalog = load_docs()
    print(f"Documentation verified: {len(catalog['pages'])} pages, {len(catalog['showcase']['items'])} showcase outputs.")


if __name__ == "__main__":
    main()
