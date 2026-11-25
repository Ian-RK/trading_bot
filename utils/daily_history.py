"""Fetch daily bars from Alpaca into memory (no files are written)."""
from datetime import timedelta

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

LOOKBACK_DAYS = 400   # about 275 trading days; SMA-200 needs 200


def fetch_daily_history(client, symbol, now, lookback_days=LOOKBACK_DAYS):
    """Return daily bars as a DataFrame. Raises ValueError if nothing comes back."""
    end = pd.Timestamp(now).to_pydatetime()
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=end - timedelta(days=lookback_days),
        end=end,
        feed=DataFeed.IEX,
    )
    df = client.get_stock_bars(req).df
    if df is None or df.empty:
        raise ValueError(f"no daily bars returned for {symbol}")
    df = df.reset_index()
    return df[["timestamp", "open", "high", "low", "close", "volume"]]