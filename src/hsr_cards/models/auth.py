"""Compatibility alias for HoYoLAB auth response models."""
import sys
from ..providers.hoyolab.models import auth as _implementation
sys.modules[__name__] = _implementation
