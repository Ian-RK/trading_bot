"""
Read-only market diagnostic. Places no orders.
Run from the repo root:  python -m scripts.diagnose_market
"""
from datetime import datetime, timezone

from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.requests import GetCalendarRequest

from utils.data_downloader import client as data_client
from utils.position_reconciler import trading_client

SYMBOL = "SPY"

print("=== MARKET DIAGNOSTIC: READ ONLY ===")
print("now (UTC):", datetime.now(timezone.utc))

# 1. Clock
clock = trading_client.get_clock()
print("\n[clock]", clock)
print("timestamp tzinfo:", clock.timestamp.tzinfo, "| next_open tzinfo:", clock.next_open.tzinfo)

# 2. Calendar (the shape main.py relies on)
today_utc = datetime.now(timezone.utc).date()
cal = trading_client.get_calendar(GetCalendarRequest(start=today_utc, end=today_utc))
print("\n[calendar] type:", type(cal).__name__, "| len:", len(cal))
for c in cal:
    print("entry:", c)
    print("  open :", type(c.open).__name__, repr(c.open), "| tzinfo:", getattr(c.open, "tzinfo", None))
    print("  close:", type(c.close).__name__, repr(c.close), "| tzinfo:", getattr(c.close, "tzinfo", None))

# 3. Latest bar per feed
print()
for feed in (None, DataFeed.IEX, DataFeed.SIP):
    label = "default" if feed is None else feed.value
    try:
        if feed is None:
            req = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
        else:
            req = StockLatestBarRequest(symbol_or_symbols=SYMBOL, feed=feed)
        bar = data_client.get_stock_latest_bar(req)[SYMBOL]
        age = (datetime.now(timezone.utc) - bar.timestamp).total_seconds()
        print(f"[bar:{label}] close={bar.close} volume={bar.volume} "
              f"timestamp={bar.timestamp} age={age:.0f}s")
    except Exception as e:
        print(f"[bar:{label}] FAILED: {str(e)[:200]}")