from __future__ import annotations


class NanokaError(Exception):
    """Base exception for the Nanoka SDK."""


class NanokaHTTPError(NanokaError):
    def __init__(self, url: str, status: int, message: str | None = None):
        self.url = url
        self.status = status
        self.message = message or f"HTTP {status}"
        super().__init__(f"{self.message} ({url})")


class NanokaNotFoundError(NanokaError):
    def __init__(self, resource: str, identifier: str | int):
        self.resource = resource
        self.identifier = str(identifier)
        super().__init__(f"{resource} {identifier!r} was not found")


class NanokaCacheError(NanokaError):
    """Raised when the local cache cannot be read, written, or validated."""


class NanokaAssetError(NanokaError):
    """Raised when an asset cannot be downloaded or resolved."""