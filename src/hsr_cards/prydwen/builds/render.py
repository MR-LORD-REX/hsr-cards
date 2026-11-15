"""Compatibility import for :mod:`hsr_cards.renderer.prydwen.builds.card`."""
import sys
from importlib import import_module

_module = import_module("hsr_cards.renderer.prydwen.builds.card")
sys.modules[__name__] = _module
