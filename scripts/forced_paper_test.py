"""
Forced 1-share PAPER order test (strategy bypassed on purpose).
Switches are flipped INSIDE THIS PROCESS ONLY, after a typed confirmation.

Run from the repo root, during market hours (about 10:00-15:30 ET):
    python -m scripts.forced_paper_test
"""
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.requests import GetCalendarRequest

import utils.order_submit as sub
from utils.broker import trading_client, verify_paper_account
from utils.data_downloader import client as data_client
from utils.data_freshness import check_bar_freshness
from utils.kill_switch import is_trading_halted
from utils.market_schedule import classify_market_time
from utils.order_reconciler import get_open_orders
from utils.position_reconciler import get_current_position
from utils.risk_management import is_account_tradable

SYMBOL = "SPY"
CONFIRM_PHRASE = "PLACE 1 PAPER SHARE"
ET = ZoneInfo("America/New_York")


def fail(message, code=1):
    print(f"[FAIL] {message}")
    sys.exit(code)


def ok(message):
    print(f"[OK]   {message}")


def latest_bar():
    request = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
    bar = data_client.get_stock_latest_bar(request)[SYMBOL]
    fresh, reason, age = check_bar_freshness(bar.timestamp, datetime.now(timezone.utc))
    return bar, fresh, reason, age


def market_state():
    now = datetime.now(timezone.utc)
    clock = trading_client.get_clock()
    today_et = now.astimezone(ET).date()
    calendar = trading_client.get_calendar(GetCalendarRequest(start=today_et, end=today_et))
    return classify_market_time(now, clock.is_open, calendar)


def equity():
    return float(trading_client.get_account().equity)


def open_orders_now():
    return get_open_orders(SYMBOL)


def show(label, result):
    print(f"\n--- {label} ---")
    for key in ("outcome", "state", "filled_qty", "qty", "limit_price",
                "client_order_id", "order_id"):
        print(f"{key:>16}: {result.get(key)}")
    print(f"{'reason':>16}: {result.get('reason')}")


def check_preconditions():
    paper_ok, why = verify_paper_account()
    if not paper_ok:
        fail(f"not a verified paper account: {why}")
    ok("verified paper account")

    tradable, why = is_account_tradable()
    if not tradable:
        fail(f"account not tradable: {why}")
    ok("account is tradable")

    state = market_state()
    if state["state"] != "OPEN":
        fail(f"market state is {state['state']} ({state['reason']}); "
             "run this during market hours")
    ok("market is OPEN")

    bar, fresh, reason, age = latest_bar()
    if not fresh:
        fail(f"latest bar is not fresh: {reason}")
    ok(f"latest bar is fresh (age {age:.0f}s), close={bar.close}")

    position = get_current_position(SYMBOL)
    if position["status"] != "OK" or position["qty"] != 0:
        fail(f"must start flat in {SYMBOL}; position query says {position}")
    ok(f"account is flat in {SYMBOL}")

    orders = open_orders_now()
    if orders["status"] != "OK" or orders["count"] != 0:
        fail(f"must start with no open {SYMBOL} orders; query says {orders}")
    ok(f"no open {SYMBOL} orders")

    halted, why = is_trading_halted()
    if halted:
        fail(f"kill switch is on: {why}")
    ok("kill switch is off")
    return bar


def main():
    print("=== FORCED 1-SHARE PAPER TEST (strategy bypassed) ===")
    bar = check_preconditions()

    print("\nThis will place REAL orders on your PAPER account:")
    print("  1) BUY 1 SPY")
    print("  2) the SAME order id again (duplicate-protection test)")
    print("  3) SELL to flatten")
    if input(f"Type exactly '{CONFIRM_PHRASE}' to continue: ").strip() != CONFIRM_PHRASE:
        fail("confirmation phrase not typed; nothing was placed")

    sub.DRY_RUN = False
    os.environ["TRADING_ENABLED"] = "true"
    try:
        ref_price, bar_time = float(bar.close), bar.timestamp
        buy_intent = {"action": "BUY", "qty": 1, "reason": "forced paper test"}

        # Step 1: BUY 1
        r1 = sub.place_order(buy_intent, SYMBOL, ref_price, bar_time, equity(), 0.0,
                             open_orders_fn=open_orders_now)
        show("Step 1: BUY 1", r1)
        if r1["outcome"] != "SUBMITTED" or r1["state"] != "DONE_FILLED":
            fail("step 1 did not end filled. CHECK THE ALPACA DASHBOARD and cancel "
                 "any open order manually.", code=2)
        pos = get_current_position(SYMBOL)
        print(f"position after step 1: {pos}")
        if pos["status"] != "OK" or pos["qty"] != 1.0:
            fail("position is not exactly 1 share. CHECK THE ALPACA DASHBOARD.", code=2)

        # Step 2: SAME order id again (same bar time, side and symbol)
        r2 = sub.place_order(buy_intent, SYMBOL, ref_price, bar_time, equity(),
                             pos["qty"], open_orders_fn=open_orders_now)
        show("Step 2: SAME order id again", r2)
        if r2["outcome"] == "SUBMIT_UNKNOWN":
            fail("step 2 outcome unknown. CHECK THE DASHBOARD and flatten manually.", code=2)

        # Step 3: flatten whatever whole shares we hold
        pos = get_current_position(SYMBOL)
        if pos["status"] != "OK":
            fail("cannot read position. CHECK THE DASHBOARD and flatten manually.", code=2)
        held = int(pos["qty"])
        print(f"\nposition before step 3: {pos}")
        bar2, fresh2, reason2, _ = latest_bar()
        if not fresh2:
            fail(f"latest bar not fresh for the sell: {reason2}. Flatten manually.", code=2)
        sell_intent = {"action": "SELL", "qty": held, "reason": "forced paper test flatten"}
        r3 = sub.place_order(sell_intent, SYMBOL, float(bar2.close), bar2.timestamp,
                             equity(), pos["qty"], open_orders_fn=open_orders_now)
        show("Step 3: SELL to flatten", r3)

        final_pos = get_current_position(SYMBOL)
        final_orders = open_orders_now()
        print(f"\nfinal position:    {final_pos}")
        print(f"final open orders: {final_orders}")
        flat = final_pos["status"] == "OK" and final_pos["qty"] == 0
        clean = final_orders["status"] == "OK" and final_orders["count"] == 0
        print("\nRESULT:", "PASSED (flat, no open orders)" if flat and clean
              else "CHECK THE ALPACA DASHBOARD")
        print(f"unresolved latch: {sub.unresolved_submission()}")
    finally:
        sub.DRY_RUN = True
        os.environ.pop("TRADING_ENABLED", None)


if __name__ == "__main__":
    main()