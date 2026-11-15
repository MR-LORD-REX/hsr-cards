"""Compatibility alias for HoYoLAB notes response models."""
import sys
from ..providers.hoyolab.models import notes as _implementation
sys.modules[__name__] = _implementation
