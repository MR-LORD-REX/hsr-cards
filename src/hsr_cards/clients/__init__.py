"""Independent clients, exposed lazily without constructing provider resources."""
from importlib import import_module

__all__ = ["HonkaiStarrail", "HoYoLABClient", "NanokaClient", "PrydwenClient"]
_MODULES = {"HonkaiStarrail": "main", "HoYoLABClient": "hoyolab", "NanokaClient": "nanoka", "PrydwenClient": "prydwen"}


def __getattr__(name: str):
    """Resolve one public client class on first access; unknown names raise AttributeError."""
    if name not in _MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
    globals()[name] = value
    return value
