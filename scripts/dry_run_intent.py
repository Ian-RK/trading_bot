"""
Read-only dry run. Fetches live paper-account state and PRINTS what
compute_order_intent would decide for each weight. Places no orders.

Run from the repo root:  python -m scripts.dry_run_intent
"""
from datetime import datetime, timezone

from alpaca.data.requests import StockLatestBarRequest

from utils.data_downloader import client as data_client
from utils.position_reconciler import trading_client, get_current_position
from utils.order_reconciler import get_open_orders
from utils.order_intent import compute_order_intent

SYMBOL = "SPY"
WEIGHTS = [1.0, 0.5, 0.0, -0.5, -1.0]


def fetch_equity():
    try:
        return float(trading_client.get_account().equity)
    except Exception as e:
        print(f"[DRY RUN] equity fetch failed: {e}")
        return None


def fetch_price():
    try:
        request = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
        bar = data_client.get_stock_latest_bar(request)[SYMBOL]
        age = (datetime.now(timezone.utc) - bar.timestamp).total_seconds()
        print(f"[DRY RUN] latest bar: close={bar.close} "
              f"timestamp={bar.timestamp} age={age:.0f}s")
        return float(bar.close)
    except Exception as e:
        print(f"[DRY RUN] price fetch failed: {e}")
        return None


if __name__ == "__main__":
    print("=== DRY RUN: NO ORDERS WILL BE PLACED ===")
    position = get_current_position(SYMBOL)
    open_orders = get_open_orders(SYMBOL)
    equity = fetch_equity()
    price = fetch_price()

    print(f"[DRY RUN] position:    {position}")
    print(f"[DRY RUN] open orders: {open_orders}")
    print(f"[DRY RUN] equity:      {equity}")
    print(f"[DRY RUN] price:       {price}")
    print()
    print(f"{'weight':>7}  {'action':<8} {'qty':>5}  reason")
    for w in WEIGHTS:
        r = compute_order_intent(w, price, equity, position, open_orders)
        print(f"{w:>7}  {r['action']:<8} {r['qty']:>5}  {r['reason']}")