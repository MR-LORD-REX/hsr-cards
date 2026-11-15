"""Compatibility alias for HoYoLAB events response models."""
import sys
from ..providers.hoyolab.models import events as _implementation
sys.modules[__name__] = _implementation
