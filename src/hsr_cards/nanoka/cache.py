"""Compatibility alias for :mod:`hsr_cards.providers.nanoka.cache`."""

import sys
from importlib import import_module

_implementation = import_module("hsr_cards.providers.nanoka.cache")
sys.modules[__name__] = _implementation
