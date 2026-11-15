"""Compatibility API for active Prydwen redeem codes."""
from __future__ import annotations
import asyncio
from ..providers.prydwen.models import RedeemCode, Reward
from ..providers.prydwen.parsing.codes import PRYDWEN_CODES_URL, parse_redeem_codes
from ..providers.prydwen.http import fetch_html as _fetch_html

async def fetch_redeem_codes(
    url: str = PRYDWEN_CODES_URL,
    *,
    timeout: float = 30.0,
) -> list[RedeemCode]:
    """Fetch active code/reward models from the public codes page.

    url defaults to Prydwen's Star Rail codes page; timeout is in seconds.
    Runs blocking HTTP in a worker and closes its scraper. An absent active
    list returns []; dependency and HTTP errors propagate. No files are written.
    """
    html = await asyncio.to_thread(_fetch_html, url, timeout)
    return parse_redeem_codes(html, base_url=url)


__all__ = ["PRYDWEN_CODES_URL", "RedeemCode", "Reward", "fetch_redeem_codes", "parse_redeem_codes"]
