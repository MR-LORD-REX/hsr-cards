from __future__ import annotations


class NanokaError(Exception):
    """Base exception for the Nanoka SDK."""


class NanokaHTTPError(NanokaError):
    """A failed HTTP request or invalid provider response.

    Carry the requested URL, HTTP status (zero when unavailable), and diagnostic
    message so callers can inspect failures without parsing the exception text.
    """
    def __init__(self, url: str, status: int, message: str | None = None):
        """Record URL, HTTP status, and optional diagnostic text without performing IO.

        A missing/empty message defaults to HTTP <status>; attributes remain available
        for structured error handling.
        """
        self.url = url
        self.status = status
        self.message = message or f"HTTP {status}"
        super().__init__(f"{self.message} ({url})")


class NanokaNotFoundError(NanokaError):
    """A requested provider resource has no published detail document.

    Carry the resource kind and string-form identifier; optional lookup methods
    may return None instead of raising this exception.
    """
    def __init__(self, resource: str, identifier: str | int):
        """Record the missing resource kind and its string-form identifier.

        The exception formats a human-readable message and performs no IO.
        """
        self.resource = resource
        self.identifier = str(identifier)
        super().__init__(f"{resource} {identifier!r} was not found")


class NanokaCacheError(NanokaError):
    """Raised when the local cache cannot be read, written, or validated."""


class NanokaAssetError(NanokaError):
    """Raised when an asset cannot be downloaded or resolved."""
