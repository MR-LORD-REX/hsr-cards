"""Compatibility alias for the HoYoLAB API transport."""
import sys
from ..providers.hoyolab import api as _implementation
sys.modules[__name__] = _implementation
