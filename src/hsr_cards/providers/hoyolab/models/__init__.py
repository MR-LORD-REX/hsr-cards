"""HoYoLAB response schemas grouped by domain."""

from .auth import Cookies
from .currencywar import CurrencyWarData, CurrencyWarResponse
from .events import CalendarData, CalendarResponse
from .notes import NotesData, NotesResponse

__all__ = ["Cookies", "CurrencyWarData", "CurrencyWarResponse", "CalendarData", "CalendarResponse", "NotesData", "NotesResponse"]
