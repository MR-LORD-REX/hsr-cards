"""Compatibility import for :mod:`hsr_cards.clients.prydwen`."""
import sys
from importlib import import_module

_module = import_module("hsr_cards.clients.prydwen")
sys.modules[__name__] = _module
