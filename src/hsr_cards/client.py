"""Compatibility alias for the main card facade and its patchable imports."""
import sys
from .clients import main as _implementation
sys.modules[__name__] = _implementation
