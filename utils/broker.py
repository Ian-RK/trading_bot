"""
Filename: broker.py
Description: The ONE place the Alpaca trading client is created. PAPER ONLY.
    check_paper_only() is a fail-closed safety check meant to run at startup.
"""

import os
from urllib.parse import urlparse

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()

PAPER_HOST = "paper-api.alpaca.markets"

# paper=True is hard-coded on purpose: there is no setting that makes this live.
trading_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True,
)


def check_paper_only(client, base_url):
    """
    Returns (ok: bool, reason: str). Fail-closed.
    1. If base_url is set, its host must be exactly the paper host
       (checked BEFORE any network call).
    2. The account number must start with 'PA' (paper account).
    """
    if base_url is not None and str(base_url).strip():
        try:
            host = urlparse(str(base_url).strip()).hostname
        except Exception:
            host = None
        if host != PAPER_HOST:
            return False, f"ALPACA_BASE_URL host is {host!r}, expected {PAPER_HOST!r}"

    try:
        account = client.get_account()
    except Exception as e:
        detail = " ".join(str(e).split())[:200]
        return False, f"account query failed: {detail}"

    number = getattr(account, "account_number", None)
    if not isinstance(number, str) or not number.startswith("PA"):
        return False, "account number does not look like a paper account (expected 'PA' prefix)"

    return True, "OK"


def verify_paper_account():
    """Runs the check against the shared client and the environment."""
    return check_paper_only(trading_client, os.getenv("ALPACA_BASE_URL"))