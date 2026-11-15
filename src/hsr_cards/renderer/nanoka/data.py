"""Compatibility alias for shared character data and rendered-cache services."""
import sys
from ...services import character_data as _implementation
sys.modules[__name__] = _implementation
