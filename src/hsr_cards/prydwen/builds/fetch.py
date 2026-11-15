"""Compatibility import for :mod:`hsr_cards.providers.prydwen.fetch`."""
import sys
from importlib import import_module

_module = import_module("hsr_cards.providers.prydwen.fetch")
sys.modules[__name__] = _module
