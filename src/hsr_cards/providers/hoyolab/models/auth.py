"""Validated HoYoLAB credentials."""

from pydantic import BaseModel

class Cookies(BaseModel):
    """Explicit ltoken/ltuid credentials; constructing this model performs no IO."""

    ltoken_v2: str
    ltuid_v2: str
