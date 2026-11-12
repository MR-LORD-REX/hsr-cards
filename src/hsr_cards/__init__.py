from .client import HonkaiStarrail

__version__ = "1.0.2"
__author__ = "sora"

__all__ = ["HonkaiStarrail", "NanokaClient", "Locale"]


def __getattr__(name: str):
    """Lazily expose the optional Nanoka SDK without changing existing imports."""
    if name in {"NanokaClient", "Locale"}:
        from .nanoka import Locale, NanokaClient

        return {"NanokaClient": NanokaClient, "Locale": Locale}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
