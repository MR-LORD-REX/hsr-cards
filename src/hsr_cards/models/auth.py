from pydantic import BaseModel
from typing import Literal

class Cookies(BaseModel):
    ltoken_v2: str
    ltuid_v2: str
