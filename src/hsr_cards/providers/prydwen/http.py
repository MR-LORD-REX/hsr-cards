"""Cloudflare-aware page HTTP access; browser collection stays separate."""
from __future__ import annotations

_HEADERS = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}

def fetch_html(url: str, timeout: float, proxy: str | None = None) -> str:
    """Fetch a page in a scoped scraper, raising on missing dependency or HTTP errors.

    The timeout is in seconds; proxy is applied to HTTP and HTTPS. The caller
    runs this blocking operation in a worker when used from async code.
    """
    try:
        import cloudscraper
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("cloudscraper is required to fetch Prydwen pages") from exc

    with cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    ) as scraper:
        if proxy:
            scraper.proxies.update({"http": proxy, "https": proxy})
        response = scraper.get(url, headers=_HEADERS, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"Prydwen returned {response.status_code} for {url}")
        return response.text

