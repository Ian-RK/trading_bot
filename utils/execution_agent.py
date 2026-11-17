"""
Filename: execution_agent.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-27-2025
Description: Decides what order (if any) a strategy weight calls for.
    THIS VERSION CANNOT SUBMIT ORDERS. It only logs the decision
    produced by compute_order_intent(). Submission is a separate,
    later feature with its own paper test.
"""

from utils.position_reconciler import trading_client, get_current_position
from utils.order_reconciler import get_open_orders
from utils.order_intent import compute_order_intent
from utils.audit_log import audit_event

# Safety switch. Must stay True: there is no submit code in this version.
DRY_RUN = True


def get_equity():
    try:
        return float(trading_client.get_account().equity)
    except Exception as e:
        print(f"[EXECUTION] equity fetch failed: {e}")
        return None


def execute_weighted_trade(symbol, weight, current_price):
    if not DRY_RUN:
        raise RuntimeError("Order submission is not implemented in this version.")

    position = get_current_position(symbol)
    open_orders = get_open_orders(symbol)
    equity = get_equity()

    intent = compute_order_intent(weight, current_price, equity, position, open_orders)
    audit_event(
        "intent",
        symbol=symbol, weight=weight, price=current_price, equity=equity,
        position_status=position.get("status"), position_qty=position.get("qty"),
        open_orders_status=open_orders.get("status"),
        open_orders_count=open_orders.get("count"),
        action=intent["action"], qty=intent["qty"], reason=intent["reason"],
        dry_run=DRY_RUN,
    )
    print(f"[EXECUTION][DRY RUN] weight={weight} price={current_price} -> {intent}")
    return None