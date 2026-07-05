from dataclasses import dataclass, field
from typing import Literal, Mapping, Optional
import hashlib
import random
import string
import time
import os


def generate_ds() -> str:
    t = int(time.time())
    DS_SALT = "6s25p5ox5y14umn1p61aqyyvbvvl3lrt"
    r = "".join(random.choices(string.ascii_letters, k=6))
    h = hashlib.md5(f"salt={DS_SALT}&t={t}&r={r}".encode()).hexdigest()
    return f"{t},{r},{h}"

def get_token(token:Literal["ltoken_v2","ltuid_v2"]) -> str | None:
    name=token
    token = os.getenv(token)
    if not token:
        raise ValueError(f"Environment variable {name} is not set. Please set it or Please check your .env file. and load it using load_dotenv()")
    return token

def get_default_uid() -> int | None:
    uid = os.getenv("default_uid")
    if not uid:
        raise ValueError("Environment variable 'default_uid' is not set. Please add it to your .env file and load it using load_dotenv()")
    return int(uid)
    
@dataclass
class BaseEndpoint:
    ANOMALY: str = 'https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_peak'
    MOC: str = 'https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge'
    PF: str = 'https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_story'
    AS: str = 'https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_boss'
    NOTES: str = 'https://sg-act-public-api.hoyolab.com/event/game_record/hkrpg/api/note'
    ACT_CALENDAR: str = 'https://sg-act-public-api.hoyolab.com/event/game_record/hkrpg/api/get_act_calender'

    cookie: Optional[Mapping[str, str]] = field(default=None)

    headers: dict = field(init=False)

    def __post_init__(self):
        if self.cookie:
            ltoken = self.cookie["ltoken_v2"]
            ltuid = self.cookie["ltuid_v2"]
        else:
            ltoken = get_token(token="ltoken_v2")
            ltuid = get_token(token="ltuid_v2")

        self.headers = {
            "ds": generate_ds(),
            "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "x-rpc-app_version": "1.5.0",
            "x-rpc-client_type": "5",
            "x-rpc-language": "en-us",
            "cookie": f"ltoken_v2={ltoken};ltuid_v2={ltuid};",
        }