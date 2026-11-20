"""
Filename: order_params.py
Description: Pure helpers for building order parameters. No API calls.
    - build_client_order_id: deterministic, unique-per-(symbol, side, bar) ID.
    - marketable_limit_price: limit slightly through the last price.
    Invalid input RAISES ValueError (never returns a blank/None value that
    could silently turn into an order with an auto-generated ID).
"""

import math
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

ID_PREFIX = "tb1"
_SYMBOL_RE = re.compile(r"^[A-Z]{1,6}$")
_PREFIX_RE = re.compile(r"^[a-z0-9]{1,10}$")
_TICK = Decimal("0.01")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def build_client_order_id(symbol, side, bar_time, prefix=ID_PREFIX):
    """e.g. tb1-SPY-buy-20261117T143500Z (letters, digits, hyphens only)."""
    if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
        raise ValueError(f"invalid symbol: {symbol!r}")
    if side not in ("BUY", "SELL"):
        raise ValueError(f"invalid side: {side!r}")
    if not isinstance(bar_time, datetime) or bar_time.tzinfo is None:
        raise ValueError(f"bar_time must be timezone-aware: {bar_time!r}")
    if not isinstance(prefix, str) or not _PREFIX_RE.match(prefix):
        raise ValueError(f"invalid prefix: {prefix!r}")

    stamp = bar_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{symbol}-{side.lower()}-{stamp}"


def marketable_limit_price(side, ref_price, offset=0.001):
    """
    BUY : ref * (1 + offset), rounded UP to the cent.
    SELL: ref * (1 - offset), rounded DOWN to the cent.
    Returns a float with at most 2 decimals.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(f"invalid side: {side!r}")
    if not _num(ref_price) or ref_price < 1.0:
        raise ValueError(f"invalid reference price: {ref_price!r}")
    if not _num(offset) or offset <= 0 or offset > 0.01:
        raise ValueError(f"invalid offset (must be >0 and <=0.01): {offset!r}")

    ref = Decimal(str(ref_price))
    off = Decimal(str(offset))

    if side == "BUY":
        price = (ref * (Decimal(1) + off)).quantize(_TICK, rounding=ROUND_CEILING)
    else:
        price = (ref * (Decimal(1) - off)).quantize(_TICK, rounding=ROUND_FLOOR)
    return float(price)