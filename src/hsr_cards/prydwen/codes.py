"""Active HSR redeem codes from Prydwen.

Prydwen is behind Cloudflare, so the page is fetched with ``cloudscraper`` in
a worker thread while the public API stays async. The active-codes list is
server-rendered, which keeps parsing dependency-free.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

PRYDWEN_CODES_URL = "https://www.prydwen.gg/star-rail/codes"
REDEEM_URL = "https://hsr.hoyoverse.com/gift?code={code}"

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

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True, slots=True)
class Reward:
    """One reward granted by a redeem code."""

    name: str
    count: int
    url: str


@dataclass(frozen=True, slots=True)
class RedeemCode:
    """One active redeem code and all rewards it grants."""

    code: str
    redeem_url: str 
    rewards: list[Reward]


def _attr(attrs: list[tuple[str, str | None]], name: str) -> str:
    for key, value in attrs:
        if key == name:
            return value or ""
    return ""


def _has_class(attrs: list[tuple[str, str | None]], name: str) -> bool:
    return name in _attr(attrs, "class").split()


def _clean_text(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", "".join(parts)).strip()


class _CodesParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.codes: list[RedeemCode] = []
        self._stack: list[str] = []
        self._active_depth: int | None = None
        self._card_depth: int | None = None
        self._card_code = ""
        self._card_code_text: list[str] = []
        self._code_depth: int | None = None
        self._rewards: list[Reward] = []
        self._reward_depth: int | None = None
        self._reward_name: list[str] = []
        self._reward_count: list[str] = []
        self._reward_icon = ""
        self._in_strong = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _VOID_TAGS:
            if self._reward_depth is not None and tag == "img" and not self._reward_icon:
                self._reward_icon = _attr(attrs, "src").strip()
            return

        self._stack.append(tag)
        depth = len(self._stack)

        if tag == "div" and _attr(attrs, "id") == "active-code-list":
            self._active_depth = depth
            return

        if self._active_depth is None:
            return

        if tag == "article" and _has_class(attrs, "code-card"):
            self._card_depth = depth
            self._card_code = _attr(attrs, "data-code").strip()
            self._card_code_text = []
            self._rewards = []
            return

        if self._card_depth is None:
            return

        if tag == "code" and self._code_depth is None:
            self._code_depth = depth
            return

        if tag == "span" and _has_class(attrs, "code-reward"):
            self._reward_depth = depth
            self._reward_name = []
            self._reward_count = []
            self._reward_icon = ""
            self._in_strong = False
            return

        if self._reward_depth is None:
            return

        if tag == "strong":
            self._in_strong = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return

        depth = len(self._stack)

        if tag == "strong" and self._in_strong:
            self._in_strong = False

        if self._reward_depth is not None and tag == "span" and depth == self._reward_depth:
            self._finish_reward()
            self._reward_depth = None
        elif self._card_depth is not None and tag == "article" and depth == self._card_depth:
            self._finish_card()
            self._card_depth = None
        elif self._code_depth is not None and tag == "code" and depth == self._code_depth:
            self._code_depth = None
        elif self._active_depth is not None and tag == "div" and depth == self._active_depth:
            self._active_depth = None

        self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._reward_depth is None:
            if self._code_depth is not None:
                self._card_code_text.append(data)
            return
        if self._in_strong:
            self._reward_count.append(data)
        else:
            self._reward_name.append(data)

    def _finish_reward(self) -> None:
        name = _clean_text(self._reward_name)
        count_text = _clean_text(self._reward_count)
        match = re.search(r"\d[\d,]*", count_text)
        count = int(match.group(0).replace(",", "")) if match else 0
        icon_url = urljoin(self.base_url, self._reward_icon) if self._reward_icon else ""
        if name:
            self._rewards.append(Reward(name=name, count=count, url=icon_url))

    def _finish_card(self) -> None:
        code = self._card_code or _clean_text(self._card_code_text)
        if not code:
            return
        redeem_url = REDEEM_URL.format(code=code)
        self.codes.append(RedeemCode(code=code, rewards=list(self._rewards), redeem_url=redeem_url))


def parse_redeem_codes(html: str, *, base_url: str = PRYDWEN_CODES_URL) -> list[RedeemCode]:
    """Parse the active-codes list from a Prydwen codes page."""
    parser = _CodesParser(base_url)
    parser.feed(html)
    parser.close()
    return parser.codes


def _fetch_html(url: str, timeout: float) -> str:
    try:
        import cloudscraper
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("cloudscraper is required to fetch Prydwen codes") from exc

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    response = scraper.get(url, headers=_HEADERS, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"Prydwen returned {response.status_code} for {url}")
    return response.text


async def fetch_redeem_codes(
    url: str = PRYDWEN_CODES_URL,
    *,
    timeout: float = 30.0,
) -> list[RedeemCode]:
    """Return active redeem codes and their rewards from Prydwen."""
    html = await asyncio.to_thread(_fetch_html, url, timeout)
    return parse_redeem_codes(html, base_url=url)


__all__ = [
    "PRYDWEN_CODES_URL",
    "RedeemCode",
    "Reward",
    "fetch_redeem_codes",
    "parse_redeem_codes",
]