"""Compatibility alias for the endgame service API and its historical helpers."""
import sys
from ...services.endgame import api as _implementation
from ...services.endgame.api import get_current_endgame_card, get_next_endgame_card
from ...services.endgame.results import EndgameCardResult, EndgameFloorCard

sys.modules[__name__] = _implementation
