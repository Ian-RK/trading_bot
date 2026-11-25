from datetime import datetime, timezone

import pandas as pd
import pytest
from alpaca.data.enums import DataFeed

from utils.daily_history import LOOKBACK_DAYS, fetch_daily_history

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, df):
        self.df = df


class _Client:
    def __init__(self, df):
        self._df = df
        self.requests = []

    def get_stock_bars(self, request):
        self.requests.append(request)
        return _Result(self._df)


def _multi_index_frame():
    idx = pd.MultiIndex.from_tuples(
        [("SPY", pd.Timestamp("2026-11-19 05:00", tz="UTC")),
         ("SPY", pd.Timestamp("2026-11-20 05:00", tz="UTC"))],
        names=["symbol", "timestamp"])
    return pd.DataFrame({"open": [1.0, 2.0], "high": [2.0, 3.0], "low": [0.5, 1.5],
                         "close": [1.5, 2.5], "volume": [10.0, 20.0],
                         "trade_count": [1, 2], "vwap": [1.4, 2.4]}, index=idx)


def test_returns_expected_columns_only():
    out = fetch_daily_history(_Client(_multi_index_frame()), "SPY", NOW)
    assert list(out.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(out) == 2


def test_empty_result_raises():
    with pytest.raises(ValueError):
        fetch_daily_history(_Client(pd.DataFrame()), "SPY", NOW)


def test_request_uses_iex_feed_and_lookback():
    client = _Client(_multi_index_frame())
    fetch_daily_history(client, "SPY", NOW)
    req = client.requests[0]
    assert req.feed == DataFeed.IEX
    start = req.start
    if start.tzinfo is None:          # the library may store it as naive UTC
        start = start.replace(tzinfo=timezone.utc)
    assert (NOW - start).days == LOOKBACK_DAYS