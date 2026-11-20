"""
Filename: order_status.py
Description: Pure classifier for Alpaca order status. No API calls.
    A status is NEVER trusted alone: it is read together with qty and
    filled_qty (an order reported 'canceled' may still have partial fills).
    Anything unrecognized or inconsistent -> UNKNOWN (which blocks new orders).
"""

import math

ACTIVE_STATUSES = frozenset({
    "new", "accepted", "pending_new", "accepted_for_bidding", "pending_review",
    "held", "partially_filled", "pending_cancel", "pending_replace", "stopped",
})
TERMINAL_BY_FILL = frozenset({"canceled", "expired", "done_for_day", "calculated"})
REJECT_LIKE = frozenset({"rejected", "suspended"})

_DONE_STATES = frozenset({"DONE_FILLED", "DONE_PARTIAL", "DONE_NOT_FILLED"})
_TOL = 1e-9


def _status_text(value):
    value = getattr(value, "value", value)      # works for enums and plain strings
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value or None


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _result(state, filled_qty, reason):
    return {"state": state, "filled_qty": filled_qty, "reason": reason}


def _unknown(reason):
    return _result("UNKNOWN", None, reason)


def classify_order(status, qty, filled_qty):
    """
    Returns {"state": ACTIVE|DONE_FILLED|DONE_PARTIAL|DONE_NOT_FILLED|UNKNOWN,
             "filled_qty": float | None, "reason": str}
    qty / filled_qty may be numbers or numeric strings (Alpaca sends strings).
    """
    s = _status_text(status)
    if s is None:
        return _unknown("missing or non-text status")

    q = _number(qty)
    f = _number(filled_qty)
    if q is None or q <= 0:
        return _unknown(f"invalid qty: {qty!r}")
    if f is None or f < 0:
        return _unknown(f"invalid filled_qty: {filled_qty!r}")
    if f > q + _TOL:
        return _unknown(f"filled_qty {f:g} exceeds qty {q:g}")

    full = abs(f - q) <= _TOL
    none_filled = f <= _TOL

    if s == "filled":
        if full:
            return _result("DONE_FILLED", f, "filled in full")
        return _unknown(f"status filled but filled_qty {f:g} != qty {q:g}")

    if s in ACTIVE_STATUSES:
        return _result("ACTIVE", f, f"order still working ({s})")

    if s in TERMINAL_BY_FILL:
        if none_filled:
            return _result("DONE_NOT_FILLED", f, f"ended ({s}) with no fills")
        if full:
            return _result("DONE_FILLED", f, f"ended ({s}) fully filled")
        return _result("DONE_PARTIAL", f,
                       f"ended ({s}) after a PARTIAL fill: {f:g} of {q:g}")

    if s in REJECT_LIKE:
        if none_filled:
            return _result("DONE_NOT_FILLED", f, f"ended ({s}) with no fills")
        return _unknown(f"status {s} but filled_qty is {f:g}")

    return _unknown(f"unrecognized or unsupported status: {s}")


def blocks_new_orders(state):
    """Fail-closed: only the three DONE_* states allow a new order."""
    return state not in _DONE_STATES