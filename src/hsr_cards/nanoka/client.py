"""Compatibility alias for :mod:`hsr_cards.clients.nanoka`."""
import sys
from importlib import import_module
_implementation = import_module("hsr_cards.clients.nanoka")
sys.modules[__name__] = _implementation
