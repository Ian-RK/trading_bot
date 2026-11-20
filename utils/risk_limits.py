"""
Filename: risk_limits.py
Description: Hard, strategy-independent caps on order and position size.
    Pure functions: no API calls. Fail-closed: invalid input -> qty 0.
    Effective cap = min(dollar cap, percent-of-equity cap).
    Caps restrict BUYS only. Sells (risk-reducing) are never blocked by caps.
    These are PAPER-phase values. Live trading needs its own, deliberately
    chosen limits; never copy these.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_order_usd: float = 1000.0
    max_order_pct: float = 0.01
    max_position_usd: float = 5000.0
    max_position_pct: float = 0.05


DEFAULT_LIMITS = RiskLimits()


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _result(qty, capped, reason):
    return {"qty": int(qty), "capped": capped, "reason": reason}


def _invalid(what):
    return _result(0, True, f"invalid input: {what}")


def _limits_valid(limits):
    return isinstance(limits, RiskLimits) and all(
        _num(v) and v > 0
        for v in (limits.max_order_usd, limits.max_order_pct,
                  limits.max_position_usd, limits.max_position_pct)
    )


def apply_caps(action, qty, price, equity, current_qty, limits=DEFAULT_LIMITS):
    """
    action:      "BUY" or "SELL"
    qty:         requested whole shares (int >= 0)
    price:       price used for sizing (> 0)
    equity:      account equity (> 0)
    current_qty: shares currently held (>= 0)
    Returns {"qty": int, "capped": bool, "reason": str}; never more than requested.
    """
    if action not in ("BUY", "SELL"):
        return _invalid(f"action {action!r}")
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
        return _invalid(f"qty {qty!r}")
    if not _num(price) or price <= 0:
        return _invalid(f"price {price!r}")
    if not _num(equity) or equity <= 0:
        return _invalid(f"equity {equity!r}")
    if not _num(current_qty) or current_qty < 0:
        return _invalid(f"current_qty {current_qty!r}")
    if not _limits_valid(limits):
        return _invalid("limits")

    if qty == 0:
        return _result(0, False, "nothing to do")

    # Sells are never blocked by caps; they are only limited to whole shares held.
    if action == "SELL":
        held = math.floor(current_qty)
        allowed = min(qty, held)
        if allowed < qty:
            return _result(allowed, True, f"sell limited to {held} whole share(s) held")
        return _result(allowed, False, "within held shares")

    # BUY
    order_cap = min(limits.max_order_usd, limits.max_order_pct * equity)
    position_cap = min(limits.max_position_usd, limits.max_position_pct * equity)
    room = position_cap - current_qty * price
    allowed_notional = min(order_cap, room)

    if allowed_notional < price:
        if room < price:
            return _result(0, True,
                           f"position cap reached (room ${max(room, 0):,.2f} < one share)")
        return _result(0, True,
                       f"order cap ${order_cap:,.2f} is below one share (${price:,.2f})")

    allowed = min(qty, math.floor(allowed_notional / price))
    if allowed < qty:
        return _result(allowed, True,
                       f"buy limited to {allowed} share(s) by caps "
                       f"(order cap ${order_cap:,.2f}, position room ${room:,.2f})")
    return _result(allowed, False, "within caps")