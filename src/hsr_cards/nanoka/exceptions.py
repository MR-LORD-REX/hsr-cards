"""Compatibility alias for :mod:`hsr_cards.providers.nanoka.exceptions`."""

import sys
from importlib import import_module

_implementation = import_module("hsr_cards.providers.nanoka.exceptions")
sys.modules[__name__] = _implementation
