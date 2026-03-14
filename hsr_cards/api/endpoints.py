from dataclasses import dataclass, field
from typing import Literal 
import hashlib
import random
import string
import time
import os


def generate_ds() -> str:
    """Generate a dynamic DS token for HoyoLab web API."""
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
    
@dataclass
class BaseEndpoint:
    ANOMALY: str ='https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_peak'
    MOC: str ='https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge'
    PF: str ='https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_story'
    AS: str ='https://sg-public-api.hoyolab.com/event/game_record/hkrpg/api/challenge_boss'

    headers: dict = field(
        default_factory=lambda: {
        "ds": generate_ds(),
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "x-rpc-app_version": "1.5.0",
        "x-rpc-client_type": "5",
        "x-rpc-language": "en-us",
        "cookie": (
            f"ltoken_v2={get_token(token="ltoken_v2")};"
            f"ltuid_v2={get_token(token="ltuid_v2")};"
        )
    })