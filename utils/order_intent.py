"""
Filename: order_intent.py
Description: Pure decision function: weight + state -> order intent.
    No API calls, no orders. Fail-closed: bad or missing data -> BLOCKED.

    Weight semantics (long-only):
      +w : BUY up to equity * w. Never sells.
      -w : SELL down to equity * (1 + w). Never buys, never shorts.
       0 : no instruction (hold).
"""

import math


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _blocked(reason):
    return {"action": "BLOCKED", "qty": 0, "reason": reason}


def _none(reason):
    return {"action": "NONE", "qty": 0, "reason": reason}


def compute_order_intent(weight, price, equity, position, open_orders):
    """
    position:    dict from get_current_position()  -> {"status", "qty", ...}
    open_orders: dict from get_open_orders()       -> {"status", "count", ...}
    Returns {"action": "NONE"|"BUY"|"SELL"|"BLOCKED", "qty": int, "reason": str}
    """
    # 1. Weight must be valid
    if not _is_number(weight) or weight < -1.0 or weight > 1.0:
        return _blocked(f"invalid weight: {weight!r}")

    # 2. 0.0 means "no instruction", not "go flat"
    if weight == 0:
        return _none("weight 0.0 = no instruction (hold)")

    # 3. Open orders: any failure or any open order blocks
    if not isinstance(open_orders, dict) or open_orders.get("status") != "OK":
        return _blocked("open-orders query failed or missing")
    count = open_orders.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return _blocked(f"invalid open-order count: {count!r}")
    if count > 0:
        return _blocked(f"{count} open order(s) already exist for this symbol")

    # 4. Position: must be a confirmed, non-short quantity
    if not isinstance(position, dict) or position.get("status") != "OK":
        return _blocked("position query failed or missing")
    qty = position.get("qty")
    if not _is_number(qty):
        return _blocked(f"invalid position qty: {qty!r}")
    if qty < 0:
        return _blocked(f"short position detected (qty={qty}); long-only bot")

    # 5. Price and equity must be sane
    if not _is_number(price) or price <= 0:
        return _blocked(f"invalid price: {price!r}")
    if not _is_number(equity) or equity <= 0:
        return _blocked(f"invalid equity: {equity!r}")

    current_value = qty * price

    # 6. Positive weight: add exposure only
    if weight > 0:
        target_value = equity * weight
        diff = target_value - current_value
        if diff <= 0:
            return _none("already at or above target; buy signals never reduce")
        shares = math.floor(diff / price)
        if shares < 1:
            return _none("gap to target is less than one share")
        return {"action": "BUY", "qty": shares,
                "reason": f"add exposure toward {weight:.0%} of equity"}

    # 7. Negative weight: reduce exposure only
    target_value = equity * (1.0 + weight)
    diff = current_value - target_value
    if diff <= 0:
        return _none("already at or below target; sell signals never add")
    shares = min(math.floor(diff / price), math.floor(qty))
    if shares < 1:
        return _none("excess over target is less than one whole share")
    return {"action": "SELL", "qty": shares,
            "reason": f"reduce exposure toward {1.0 + weight:.0%} of equity"}