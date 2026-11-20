"""
Filename: order_submit.py
Description: The ONLY place an order can be submitted (PAPER ONLY via the shared
    broker client). Layers, in order: unresolved-submission latch, kill switch,
    intent sanity, hard caps, unique client order ID, marketable-limit price,
    TWO switches (DRY_RUN constant AND TRADING_ENABLED=true in .env), fresh
    open-orders re-check, ONE submit attempt (never auto-retried), status
    polling via classify_order, lookup by client order ID if anything fails.
    An unresolved submission latches: nothing else is submitted until cleared.
"""

import os
import time

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest
from dotenv import load_dotenv

from utils.order_params import build_client_order_id, marketable_limit_price
from utils.order_status import classify_order
from utils.risk_limits import DEFAULT_LIMITS, apply_caps

load_dotenv()

DRY_RUN = True              # switch 1 (code). Must be False AND TRADING_ENABLED=true.
POLL_SECONDS = 30
POLL_INTERVAL_SECONDS = 2

_unresolved_id = None


def trading_enabled():
    """Switch 2 (.env): exactly 'true' (case-insensitive). Default: off."""
    return os.getenv("TRADING_ENABLED", "").strip().lower() == "true"


def unresolved_submission():
    return _unresolved_id


def clear_unresolved_submission():
    """Call ONLY after verifying the order's real status at the broker."""
    global _unresolved_id
    _unresolved_id = None


def _oneline(e):
    return " ".join(str(e).split())[:200]


def _http_status(error):
    """HTTP status carried by an API error, or None if it has none."""
    try:
        status = getattr(error, "status_code", None)
    except Exception:
        return None
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def _result(outcome, reason, symbol, **extra):
    result = {
        "outcome": outcome, "reason": reason, "symbol": symbol,
        "client_order_id": None, "order_id": None, "side": None, "qty": None,
        "limit_price": None, "state": None, "filled_qty": None,
    }
    result.update(extra)
    return result


def place_order(intent, symbol, ref_price, bar_time, equity, current_qty,
                open_orders_fn, client=None, halted_fn=None, audit=None,
                limits=DEFAULT_LIMITS, sleep=time.sleep, clock=time.monotonic):
    """
    Returns a dict with outcome in:
      NOT_SUBMITTED  - a guard stopped it; nothing was sent
      DRY_RUN        - everything checked out, but a switch is off; nothing sent
      SUBMITTED      - submit accepted; 'state' is the classified order state
      RECOVERED      - submit raised, but an order with this client ID exists
      REJECTED       - broker refused (HTTP 4xx) and no order exists with this client ID;
                       nothing was placed; no latch
      SUBMIT_UNKNOWN - submit raised and the lookup failed; latch engaged
    """
    global _unresolved_id

    if audit is None:
        from utils.audit_log import audit_event as audit
    if halted_fn is None:
        from utils.kill_switch import is_trading_halted as halted_fn

    def finish(outcome, reason, **extra):
        result = _result(outcome, reason, symbol, **extra)
        audit("order_submit", **result)
        return result

    # 1. Unresolved earlier submission
    if _unresolved_id is not None:
        return finish("NOT_SUBMITTED",
                      f"unresolved earlier submission ({_unresolved_id}); "
                      "verify at the broker, then clear it")

    # 2. Kill switch (fail-closed)
    try:
        halted, why = halted_fn()
    except Exception:
        halted, why = True, "kill switch check failed"
    if halted:
        return finish("NOT_SUBMITTED", f"kill switch: {why}")

    # 3. Intent sanity
    action = intent.get("action") if isinstance(intent, dict) else None
    req_qty = intent.get("qty") if isinstance(intent, dict) else None
    if (action not in ("BUY", "SELL") or isinstance(req_qty, bool)
            or not isinstance(req_qty, int) or req_qty <= 0):
        why = intent.get("reason") if isinstance(intent, dict) else "no intent"
        return finish("NOT_SUBMITTED", f"no actionable intent: {why}")

    # 4. Hard caps (buys only; sells are limited to shares held)
    capped = apply_caps(action, req_qty, ref_price, equity, current_qty, limits)
    qty = capped["qty"]
    if qty <= 0:
        return finish("NOT_SUBMITTED", f"caps: {capped['reason']}", side=action)

    # 5. Order parameters (also validates SDK compatibility on a dry run)
    try:
        cid = build_client_order_id(symbol, action, bar_time)
        price = marketable_limit_price(action, ref_price)
        request = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            limit_price=price,
            client_order_id=cid,
        )
    except Exception as e:
        return finish("NOT_SUBMITTED", f"invalid order parameters: {_oneline(e)}",
                      side=action, qty=qty)

    details = {"client_order_id": cid, "side": action, "qty": qty, "limit_price": price}

    # 6. Two switches
    if DRY_RUN:
        return finish("DRY_RUN", "dry run: DRY_RUN constant is True; nothing submitted",
                      **details)
    if not trading_enabled():
        return finish("DRY_RUN", "TRADING_ENABLED is not 'true'; nothing submitted",
                      **details)

    # 7. Fresh open-orders re-check
    try:
        oo = open_orders_fn()
    except Exception:
        oo = None
    count = oo.get("count") if isinstance(oo, dict) else None
    if (not isinstance(oo, dict) or oo.get("status") != "OK"
            or not isinstance(count, int) or isinstance(count, bool) or count != 0):
        return finish("NOT_SUBMITTED",
                      "open-orders re-check failed or found open orders", **details)

    if client is None:
        from utils.broker import trading_client as client

    # 8. ONE submit attempt (never auto-retried)
    audit("order_submit_attempt", symbol=symbol, **details)
    order = None
    submit_error = None
    try:
        order = client.submit_order(order_data=request)
    except Exception as e:
        submit_error = _oneline(e)
        submit_status = _http_status(e)
        # 9. Resolve by client order ID; never resubmit
        try:
            order = client.get_order_by_client_id(cid)
        except Exception as lookup_exc:
            clean_refusal = (
                submit_status is not None
                and 400 <= submit_status < 500
                and submit_status != 408
                and _http_status(lookup_exc) == 404
            )
            if clean_refusal:
                return finish("REJECTED",
                              f"broker refused the order ({submit_error}); no order "
                              "exists with this client ID; nothing placed", **details)
            _unresolved_id = cid
            return finish("SUBMIT_UNKNOWN",
                          f"submit failed ({submit_error}); lookup by client ID also "
                          "failed; status unknown, new orders blocked", **details)

    # 10. Poll the status
    outcome = "SUBMITTED" if submit_error is None else "RECOVERED"

    def classify(o):
        return classify_order(getattr(o, "status", None), getattr(o, "qty", None),
                              getattr(o, "filled_qty", None))

    cls = classify(order)
    deadline = clock() + POLL_SECONDS
    while cls["state"] == "ACTIVE" and clock() < deadline:
        sleep(POLL_INTERVAL_SECONDS)
        try:
            order = client.get_order_by_client_id(cid)
            cls = classify(order)
        except Exception:
            cls = {"state": "UNKNOWN", "filled_qty": None,
                   "reason": "status lookup failed while polling"}

    if cls["state"] == "UNKNOWN":
        _unresolved_id = cid

    reason = cls["reason"]
    if submit_error is not None:
        reason = f"submit raised ({submit_error}); order found by client ID: {reason}"

    oid = getattr(order, "id", None)
    return finish(outcome, reason, order_id=None if oid is None else str(oid),
                  state=cls["state"], filled_qty=cls["filled_qty"], **details)