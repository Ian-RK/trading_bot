"""
Dry run of the guarded submit path on REAL paper data.
The client passed in refuses every write/lookup, so no order can be placed.
It writes 'order_submit' records to logs/audit.jsonl (local, git-ignored).

Run from the repo root:  python -m scripts.dry_run_submit
"""
from alpaca.data.requests import StockLatestBarRequest

from utils.data_downloader import client as data_client
from utils.order_intent import compute_order_intent
from utils.order_reconciler import get_open_orders
from utils.order_submit import DRY_RUN, place_order, trading_enabled
from utils.position_reconciler import get_current_position, trading_client

SYMBOL = "SPY"


class NoSubmitClient:
    def submit_order(self, *args, **kwargs):
        raise RuntimeError("blocked: dry-run script")

    def get_order_by_client_id(self, *args, **kwargs):
        raise RuntimeError("blocked: dry-run script")


if __name__ == "__main__":
    print("=== DRY RUN OF THE SUBMIT PATH: NO ORDER CAN BE PLACED ===")
    print(f"DRY_RUN={DRY_RUN}  TRADING_ENABLED={trading_enabled()}")

    bar = data_client.get_stock_latest_bar(
        StockLatestBarRequest(symbol_or_symbols=SYMBOL))[SYMBOL]
    equity = float(trading_client.get_account().equity)
    position = get_current_position(SYMBOL)
    open_orders = get_open_orders(SYMBOL)
    print(f"price={bar.close} bar_time={bar.timestamp} equity={equity} "
          f"position_qty={position.get('qty')}")

    for weight in (1.0, -1.0):
        intent = compute_order_intent(weight, bar.close, equity, position, open_orders)
        print(f"\nweight {weight:>4}: intent -> {intent}")
        result = place_order(
            intent, SYMBOL, bar.close, bar.timestamp, equity, position.get("qty"),
            open_orders_fn=lambda: get_open_orders(SYMBOL),
            client=NoSubmitClient(),
        )
        print(f"           submit -> {result}")