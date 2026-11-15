"""HoYoLAB endpoints and request headers, resolved only when requested.

Environment values are never loaded from a file by this module. Applications
using default credentials must load or set their own environment explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
import random
import string
import time
from typing import Literal, Mapping


def check_cookies() -> None:
    """Raise ValueError when the three default-credential environment values are absent.

    This optional compatibility helper does not load dotenv files or print secrets.
    Explicit Cookies objects do not require any environment configuration.
    """
    if not all(os.getenv(name) for name in ("ltoken_v2", "ltuid_v2", "default_uid")):
        raise ValueError("Set ltoken_v2, ltuid_v2, and default_uid in the environment, or pass explicit cookies and a UID.")


def generate_ds() -> str:
    """Generate the timestamp, nonce, and digest required by HoYoLAB headers."""
    timestamp = int(time.time())
    salt = "6s25p5ox5y14umn1p61aqyyvbvvl3lrt"
    nonce = "".join(random.choices(string.ascii_letters, k=6))
    digest = hashlib.md5(f"salt={salt}&t={timestamp}&r={nonce}".encode()).hexdigest()
    return f"{timestamp},{nonce},{digest}"


def get_token(token: Literal["ltoken_v2", "ltuid_v2"]) -> str:
    """Read one default credential from the environment or raise ValueError.

    The value is never printed and no credential file is opened.
    """
    value = os.getenv(token)
    if not value:
        raise ValueError(f"Environment variable {token} is not set; pass explicit cookies or configure the environment.")
    return value


def get_default_uid() -> int:
    """Return the configured public-calendar UID, raising ValueError if absent or invalid."""
    value = os.getenv("default_uid")
    if not value:
        raise ValueError("Environment variable default_uid is not set; configure the public-calendar account explicitly.")
    return int(value)


@dataclass
class BaseEndpoint:
    """Endpoint URLs and headers for one explicit/default HoYoLAB credential pair."""

    ANOMALY: str = "https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_peak"
    MOC: str = "https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge"
    PF: str = "https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_story"
    AS: str = "https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_boss"
    NOTES: str = "https://sg-act-public-api.hoyolab.com/event/game_record/hkrpg/api/note"
    ACT_CALENDAR: str = "https://sg-act-public-api.hoyolab.com/event/game_record/hkrpg/api/get_act_calender"
    CURRENCY_WAR: str = "https://sg-act-public-api.hoyolab.com/event/game_record/hkrpg/api/grid_fight"
    cookie: Mapping[str, str] | None = None
    headers: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        ltoken = self.cookie["ltoken_v2"] if self.cookie else get_token("ltoken_v2")
        ltuid = self.cookie["ltuid_v2"] if self.cookie else get_token("ltuid_v2")
        self.headers = {
            "ds": generate_ds(),
            "sec-ch-ua": '\"Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"145\", \"Chromium\";v=\"145\"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "x-rpc-app_version": "1.5.0",
            "x-rpc-client_type": "5",
            "x-rpc-language": "en-us",
            "cookie": f"ltoken_v2={ltoken};ltuid_v2={ltuid};",
        }
