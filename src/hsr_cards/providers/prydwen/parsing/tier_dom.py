"""Small HTML tree for server-rendered tier-list cards."""
from __future__ import annotations


import re


from html.parser import HTMLParser


_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _Node:
    __slots__ = ("tag", "attrs", "children", "parts")

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Node] = []
        self.parts: list[str | _Node] = []

    @property
    def classes(self) -> list[str]:
        """Return this node's CSS class tokens, or an empty list if absent."""
        return (_attr(self.attrs, "class")).split()

    def _text(self) -> str:
        return "".join(part if isinstance(part, str) else part._text() for part in self.parts)

    def text(self) -> str:
        """Return descendant text in document order with whitespace collapsed."""
        return _clean_text(self._text())


def _attr(attrs: list[tuple[str, str | None]], name: str) -> str:
    for key, value in attrs:
        if key == name:
            return value or ""
    return ""


def _has_class(node: _Node | None, name: str) -> bool:
    return node is not None and name in node.classes


def _find_all(
    node: _Node | None,
    *,
    tag: str | None = None,
    class_name: str | None = None,
) -> list[_Node]:
    if node is None:
        return []
    found: list[_Node] = []
    for child in node.children:
        if (tag is None or child.tag == tag) and (
            class_name is None or class_name in child.classes
        ):
            found.append(child)
        found.extend(_find_all(child, tag=tag, class_name=class_name))
    return found


def _find_first(
    node: _Node | None,
    *,
    tag: str | None = None,
    class_name: str | None = None,
) -> _Node | None:
    if node is None:
        return None
    for child in node.children:
        if (tag is None or child.tag == tag) and (
            class_name is None or class_name in child.classes
        ):
            return child
        found = _find_first(child, tag=tag, class_name=class_name)
        if found is not None:
            return found
    return None


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", [])
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Append a parsed element to the current parent and enter non-void elements."""
        node = _Node(tag.lower(), attrs)
        self._stack[-1].children.append(node)
        self._stack[-1].parts.append(node)
        if tag.lower() not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Append a self-closing element without entering its children."""
        node = _Node(tag.lower(), attrs)
        self._stack[-1].children.append(node)
        self._stack[-1].parts.append(node)

    def handle_endtag(self, tag: str) -> None:
        """Unwind to a matching ancestor; tolerate unmatched closing tags."""
        tag = tag.lower()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        """Append an HTML text segment while preserving its order among child nodes."""
        self._stack[-1].parts.append(data)


def _parse_dom(html: str) -> _Node:
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    return parser.root

