"""Compatibility import for :mod:`hsr_cards.providers.prydwen.browser_fetch`."""
import sys
from importlib import import_module

_module = import_module("hsr_cards.providers.prydwen.browser_fetch")
sys.modules[__name__] = _module
