"""
Filename: main.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: This script is a loop that now performs the 
Data Sanity Check first, then the PDT Guard, generates the 
signal, and finally triggers the trade.
"""

import time
import html
import signal
import sys
import pandas as pd
from datetime import datetime, timezone, timedelta

# Import your custom modules
from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.requests import GetCalendarRequest
from zoneinfo import ZoneInfo
from utils.market_schedule import classify_market_time

from utils.tele_monitor import send_telegram_message
from utils.risk_management import is_account_tradable, trading_client
from utils.data_downloader import client as data_client
from utils.execution_agent import execute_weighted_trade
from utils.data_freshness import check_bar_freshness
from utils.bar_tracker import BarTracker
from utils.broker import verify_paper_account
from utils.kill_switch import is_trading_halted
from utils.audit_log import audit_event
from strategies.price_action_strategy import engineer_features

# SETTINGS
SYMBOL = "SPY"
# Measured 2026-11-13: free-plan API bars are real-time IEX (~65-106s old
# at the moment of fetch), not 15-minute delayed SIP.
MAX_BAR_AGE_SECONDS = 180
_stale_alerted = False         # alert de-duplication for stale data
BUFFER_MINUTES = 3             # Safety lead/lag for market hours
EXIT_WINDOW_MINUTES = 20       # Time after close to process final bars (15 delay + 5 margin)
ET = ZoneInfo("America/New_York")
IDLE_SLEEP_SECONDS = 60        # re-check interval when the market is not open
MAX_CONSECUTIVE_FAILURES = 5   # stop the bot after this many failed cycles in a row

_last_block_reason = None      # alert de-duplication for "account not tradable"
_bar_tracker = BarTracker()    # last fully processed bar (in memory)
_halt_alerted = False          # alert de-duplication for suppressed signals

# --- MANUAL SHUTDOWN HANDLER ---
def manual_shutdown(sig, frame):
    print("\nSHUTDOWN SIGNAL RECEIVED.")
    send_telegram_message("🛑 <b>Bot shutting down manually...</b>")

    # Add logic here to close positions if desired
    try:
        # CRITICAL SAFETY: Cancel unfilled orders before going offline
        trading_client.cancel_orders()
        print("Safety: All open orders cancelled.")
    except Exception as e:
        print(f"Cleanup Warning: {e}")
    sys.exit(0)

# Register the handler for Ctrl+C (SIGINT)
signal.signal(signal.SIGINT, manual_shutdown)

def data_is_fresh(latest_bar_time):
    """True only if the bar is fresh. One Telegram alert per stale period."""
    global _stale_alerted
    ok, reason, age = check_bar_freshness(
        latest_bar_time, datetime.now(timezone.utc),
        max_age_seconds=MAX_BAR_AGE_SECONDS,
    )
    if ok:
        _stale_alerted = False
        return True

    error_msg = f"STALE/INVALID DATA for {SYMBOL}: {reason}. Vetoing trade."
    print(error_msg)
    if not _stale_alerted:
        send_telegram_message(f"⚠️ {html.escape(error_msg)}")
        _stale_alerted = True
    return False

def get_market_state():
    """
    Returns {"state": OPEN|WARMUP|COOLDOWN|CLOSED|UNKNOWN, "reason": str}.
    Any failure -> UNKNOWN (never trade).
    """
    try:
        now = datetime.now(timezone.utc)
        clock = trading_client.get_clock()
        today_et = now.astimezone(ET).date()
        calendar = trading_client.get_calendar(
            GetCalendarRequest(start=today_et, end=today_et)
        )
        return classify_market_time(
            now, clock.is_open, calendar,
            buffer_minutes=BUFFER_MINUTES,
            exit_window_minutes=EXIT_WINDOW_MINUTES,
        )
    except Exception as e:
        detail = " ".join(str(e).split())[:200]   # collapse \r\n and whitespace
        return {"state": "UNKNOWN",
                "reason": f"market state query failed: {detail}"}

"""
@brief This function checks if the live bar is safe to be traded
"""
def run_trading_cycle():
    global _last_block_reason, _halt_alerted
    print(f"\n--- Cycle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    # 1. Fetch live data
    request_params = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
    latest_bar_dict = data_client.get_stock_latest_bar(request_params)
    latest_bar = latest_bar_dict[SYMBOL]

    current_price = latest_bar.close
    bar_time = latest_bar.timestamp

    # 2. Data integrity and risk guards
    if not data_is_fresh(bar_time):
        audit_event("cycle", outcome="SKIPPED_STALE", symbol=SYMBOL,
                    bar_ts=bar_time, price=current_price)
        return

    if not _bar_tracker.is_new(bar_time):
        print(f"SKIP: bar {bar_time} already processed.")
        audit_event("cycle", outcome="SKIPPED_DUPLICATE", symbol=SYMBOL,
                    bar_ts=bar_time, price=current_price)
        return

    ok, reason = is_account_tradable()
    if not ok:
        reason = " ".join(str(reason).split())[:200]
        print(f"BLOCKED: account not tradable ({reason})")
        if reason != _last_block_reason:
            send_telegram_message(f"⛔ <b>Trading blocked</b>\n{html.escape(reason)}")
            _last_block_reason = reason
        audit_event("cycle", outcome="BLOCKED_ACCOUNT", symbol=SYMBOL,
                    bar_ts=bar_time, price=current_price, reason=reason)
        return
    _last_block_reason = None

    # 3. DATA FUSION: Injecting the live bar into historical data
    hist_df = pd.read_csv(f"data/{SYMBOL}_historical.csv")

    live_row = pd.DataFrame([{
        'timestamp': latest_bar.timestamp,
        'open': latest_bar.open,
        'high': latest_bar.high,
        'low': latest_bar.low,
        'close': latest_bar.close,
        'volume': latest_bar.volume
    }])

    full_df = pd.concat([hist_df, live_row], ignore_index=True)

    # 4. Generate Signal from the 'Fused' data
    processed_df = engineer_features(full_df)
    latest_signal = processed_df['signal_weight'].iloc[-1]

    # 5. Kill switch, then Execution Agent
    halted, halt_reason = is_trading_halted()
    if not halted:
        _halt_alerted = False

    if latest_signal != 0 and halted:
        print(f"HALTED: {halt_reason}. Signal {latest_signal} NOT executed.")
        if not _halt_alerted:
            send_telegram_message(
                f"🛑 <b>Trading halted</b>\n{html.escape(halt_reason)}\n"
                f"Signal {latest_signal} not executed."
            )
            _halt_alerted = True
        outcome = "HALTED_SIGNAL_SUPPRESSED"
    elif latest_signal != 0:
        order = execute_weighted_trade(SYMBOL, latest_signal, current_price)
        if order:
            side_str = order.side.value.upper()
            msg = f"✅ <b>{side_str} ORDER PLACED</b>\nQty: {order.qty} {SYMBOL} @ ${current_price:.2f}"
            print(msg)
            send_telegram_message(msg)
        outcome = "EXECUTION_CALLED"
    else:
        print("LOGIC: No signal detected. Holding cash/shares.")
        outcome = "NO_SIGNAL"

    audit_event("cycle", outcome=outcome, symbol=SYMBOL, bar_ts=bar_time,
                price=current_price, signal=latest_signal, halted=halted)
    _bar_tracker.mark_processed(bar_time)

def startup_check():
    """True only if the account is verified as a paper account."""
    ok, reason = verify_paper_account()
    if ok:
        return True
    detail = " ".join(str(reason).split())[:200]
    print(f"STARTUP REFUSED: {detail}")
    send_telegram_message(f"⛔ <b>Startup refused</b>\n{html.escape(detail)}")
    return False

def main_loop():
    last_state = None
    consecutive_failures = 0
    while True:
        result = get_market_state()
        state = result["state"]

        if state != last_state:
            msg = f"Market state: {state} ({result['reason']})"
            print(msg)
            send_telegram_message(f"🕒 {html.escape(msg)}")
            last_state = state
            audit_event("market_state", state=state, reason=result["reason"])

        if state == "OPEN":
            try:
                run_trading_cycle()
                consecutive_failures = 0
                time.sleep(60)
            except Exception as e:
                consecutive_failures += 1
                detail = " ".join(str(e).split())[:200]
                print(f"CYCLE ERROR ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {detail}")
                audit_event("cycle_error", count=consecutive_failures, detail=detail)
                if consecutive_failures == 1:
                    send_telegram_message(
                        f"⚠️ <b>Cycle error</b> (will retry)\n{html.escape(detail)}"
                    )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(
                        f"{MAX_CONSECUTIVE_FAILURES} consecutive cycle failures; last: {detail}"
                    )
                time.sleep(min(60 * consecutive_failures, 300))
        else:
            # WARMUP / COOLDOWN / CLOSED / UNKNOWN: never trade
            time.sleep(IDLE_SLEEP_SECONDS)


if __name__ == "__main__":
    if not startup_check():
        sys.exit(1)
    send_telegram_message("🤖 <b>Bot Active in Paper Mode</b>")
    try:
        main_loop()
    except Exception as e:
        detail = " ".join(str(e).split())[:300]
        send_telegram_message(
            f"🚨 <b>CRITICAL ERROR:</b> Bot stopped!\n{html.escape(detail)}"
        )