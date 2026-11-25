from datetime import datetime, timezone

import pytest

from utils.daily_history import DailyHistoryCache

MON_10 = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)
MON_14 = datetime(2026, 11, 23, 19, 0, tzinfo=timezone.utc)
MON_22_ET = datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)   # still Nov 23 in ET
TUE_10 = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)


def test_fetches_once_per_day():
    calls = []
    cache = DailyHistoryCache(lambda now: calls.append(now) or "DF")
    assert cache.get(MON_10) == "DF"
    cache.get(MON_14)
    assert len(calls) == 1


def test_new_day_refetches():
    calls = []
    cache = DailyHistoryCache(lambda now: calls.append(now) or "DF")
    cache.get(MON_10)
    cache.get(TUE_10)
    assert len(calls) == 2


def test_day_boundary_is_eastern():
    calls = []
    cache = DailyHistoryCache(lambda now: calls.append(now) or "DF")
    cache.get(MON_10)
    cache.get(MON_22_ET)
    assert len(calls) == 1


def test_failure_is_not_cached():
    state = {"n": 0}

    def fetch(now):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("network down")
        return "DF"

    cache = DailyHistoryCache(fetch)
    with pytest.raises(RuntimeError):
        cache.get(MON_10)
    assert cache.get(MON_10) == "DF"
    assert state["n"] == 2