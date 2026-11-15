"""Compatibility alias for HoYoLAB endpoint and credential helpers."""
import sys
from ..providers.hoyolab import endpoints as _implementation
sys.modules[__name__] = _implementation
