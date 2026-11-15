"""Compatibility alias for HoYoLAB currencywar response models."""
import sys
from ..providers.hoyolab.models import currencywar as _implementation
sys.modules[__name__] = _implementation
