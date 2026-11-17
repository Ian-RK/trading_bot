"""
Read-only probe. Fetches the latest 1-minute bar every 10 seconds for 3
minutes and prints whether it changes. Places no orders.

Run during market hours:  python -m scripts.probe_bar_formation
"""
import time
from datetime import datetime, timezone

from alpaca.data.requests import StockLatestBarRequest
from utils.data_downloader import client as data_client

SYMBOL = "SPY"
DURATION_SECONDS = 180
INTERVAL_SECONDS = 10

print("=== BAR PROBE: READ ONLY ===")
start = time.time()
previous = None
while time.time() - start < DURATION_SECONDS:
    try:
        request = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
        bar = data_client.get_stock_latest_bar(request)[SYMBOL]
        now = datetime.now(timezone.utc)
        age = (now - bar.timestamp).total_seconds()
        key = (bar.timestamp, bar.volume, bar.close)
        flag = "" if key == previous else "  <-- changed"
        print(f"{now:%H:%M:%S}Z bar_ts={bar.timestamp:%H:%M:%S} "
              f"close={bar.close} volume={bar.volume} age={age:.0f}s{flag}")
        previous = key
    except Exception as e:
        print("probe error:", " ".join(str(e).split())[:150])
    time.sleep(INTERVAL_SECONDS)