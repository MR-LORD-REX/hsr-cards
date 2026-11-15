from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import aiohttp

from .exceptions import NanokaHTTPError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

DEFAULT_ACCEPT = "*/*"


@dataclass
class HTTPResponse:
    """Response bytes and metadata returned by the Nanoka HTTP transport.

    Empty bytes/status zero are defaults. ETag and Last-Modified support disk-cache
    revalidation; from_cache marks a 304 response rather than supplying cached bytes.
    """
    body: bytes = b""
    status: int = 0
    etag: str | None = None
    last_modified: str | None = None
    content_type: str | None = None
    from_cache: bool = False

    @property
    def not_modified(self) -> bool:
        """Return whether the HTTP response is a 304 cache revalidation result."""
        return self.status == 304


class AsyncHTTP:
    """Small aiohttp wrapper with retries, revalidation, and a browser UA."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        proxy: str | None = None,
        concurrency: int = 16,
        headers: dict[str, str] | None = None,
    ):
        """Configure a lazily opened HTTP transport without starting a request/session.

        timeout is a total request deadline in seconds (30 by default); retries and
        concurrency are clamped to at least one. Optional headers override the browser
        User-Agent/Accept defaults; proxy is forwarded to requests. Async context entry
        or the first request opens an owned aiohttp session, which close() releases.
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.retries = max(1, retries)
        self.proxy = proxy
        self.headers = {"User-Agent": USER_AGENT, "Accept": DEFAULT_ACCEPT}
        if headers:
            self.headers.update(headers)
        self._session: aiohttp.ClientSession | None = None
        self._session_loop: asyncio.AbstractEventLoop | None = None
        self._close_lock: asyncio.Lock | None = None
        self._close_lock_loop: asyncio.AbstractEventLoop | None = None
        self.concurrency = max(1, concurrency)
        self._semaphore: asyncio.Semaphore | None = None
        self._semaphore_loop: asyncio.AbstractEventLoop | None = None

    async def __aenter__(self) -> "AsyncHTTP":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Return a semaphore bound to the running loop.

        aiohttp clients may outlive ``asyncio.run()`` in scripts/tests; a
        semaphore created on a closed loop would otherwise hang forever.
        """
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._semaphore_loop is not loop:
            self._semaphore = asyncio.Semaphore(self.concurrency)
            self._semaphore_loop = loop
        return self._semaphore

    async def _get_session(self) -> aiohttp.ClientSession:
        loop = asyncio.get_running_loop()
        if self._session is not None and self._session_loop is not loop:
            # aiohttp sessions are bound to an event loop. Drop a session left
            # by a previous asyncio.run() instead of hanging on it.
            self._session = None
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout, headers=self.headers)
            self._session_loop = loop
        return self._session

    def _get_close_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._close_lock is None or self._close_lock_loop is not loop:
            self._close_lock = asyncio.Lock()
            self._close_lock_loop = loop
        return self._close_lock

    async def close(self) -> None:
        """Close the owned aiohttp session on its event loop; repeated calls are safe."""
        async with self._get_close_lock():
            if self._session is not None and not self._session.closed:
                await self._session.close()
            self._session = None
            self._session_loop = None

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        allow_404: bool = False,
        use_cache: bool = False,
        cache: Any | None = None,
    ) -> HTTPResponse:
        """Fetch bytes/metadata with retries, concurrency limits, and optional validators.

        allow_404=True returns an empty 404 response. use_cache=True reads conditional
        headers from cache.validator(url); 304 preserves cached bodies. Per-call headers
        override defaults. Exhausted transport failures and unaccepted HTTP errors raise
        NanokaHTTPError; the lazily opened aiohttp session remains owned by this wrapper.
        """
        request_headers = dict(headers or {})
        if use_cache and cache is not None:
            validator = cache.validator(url) if hasattr(cache, "validator") else None
            if validator:
                if asyncio.iscoroutine(validator):
                    validator = await validator
            if validator:
                request_headers.update(validator)

        last_error: Exception | None = None
        last_status = 0
        for attempt in range(self.retries):
            try:
                session = await self._get_session()
                async with self._get_semaphore():
                    async with session.get(url, headers=request_headers, proxy=self.proxy) as response:
                        status = response.status
                        last_status = status
                        if status == 404 and allow_404:
                            return HTTPResponse(
                                status=404,
                                etag=response.headers.get("ETag"),
                                last_modified=response.headers.get("Last-Modified"),
                            )
                        if status == 304:
                            return HTTPResponse(
                                status=304,
                                from_cache=True,
                                etag=response.headers.get("ETag"),
                                last_modified=response.headers.get("Last-Modified"),
                            )
                        if status >= 400:
                            message = await response.text()
                            if status in {429, 500, 502, 503, 504} and attempt + 1 < self.retries:
                                await asyncio.sleep(0.5 * (attempt + 1))
                                last_error = NanokaHTTPError(url, status, message[:300])
                                continue
                            raise NanokaHTTPError(url, status, message[:300])
                        body = await response.read()
                        return HTTPResponse(
                            body=body,
                            status=status,
                            etag=response.headers.get("ETag"),
                            last_modified=response.headers.get("Last-Modified"),
                            content_type=response.headers.get("Content-Type"),
                        )
            except NanokaHTTPError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    await asyncio.sleep(0.35 * (attempt + 1))
        raise NanokaHTTPError(url, last_status, f"request failed: {last_error}")

    async def get_json(self, url: str, *, allow_404: bool = False) -> Any | None:
        """Fetch/decode UTF-8 JSON, or return None for an empty body or allowed 404.

        allow_404 defaults to False. Invalid JSON and request failures raise
        NanokaHTTPError; HTTP session/retry ownership follows get().
        """
        response = await self.get(url, allow_404=allow_404)
        if not response.body:
            return None
        try:
            return json.loads(response.body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NanokaHTTPError(url, 0, f"invalid JSON: {exc}") from exc


__all__ = ["AsyncHTTP", "HTTPResponse", "USER_AGENT"]
