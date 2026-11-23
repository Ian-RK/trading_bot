from datetime import datetime, timezone

import pandas as pd
from pandas.testing import assert_frame_equal

from utils.daily_bars import completed_daily_bars, history_age_days, is_history_fresh

MON_10AM_ET = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)


def _df(*stamps):
    return pd.DataFrame({"timestamp": list(stamps), "close": range(len(stamps))})


def test_drops_today_keeps_previous_day():
    df = _df("2026-11-20 05:00:00+00:00", "2026-11-23 05:00:00+00:00")
    out = completed_daily_bars(df, MON_10AM_ET)
    assert len(out) == 1
    assert out["timestamp"].iloc[0] == "2026-11-20 05:00:00+00:00"


def test_day_boundary_is_eastern_not_utc():
    # 03:00 UTC on Nov 24 is still Nov 23 at 22:00 ET, so the Nov 23 bar is "today".
    now = datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)
    df = _df("2026-11-20 05:00:00+00:00", "2026-11-23 05:00:00+00:00")
    assert len(completed_daily_bars(df, now)) == 1


def test_input_is_not_mutated():
    df = _df("2026-11-20 05:00:00+00:00", "2026-11-23 05:00:00+00:00")
    before = df.copy()
    completed_daily_bars(df, MON_10AM_ET)
    assert_frame_equal(df, before)


def test_all_rows_today_gives_empty_and_not_fresh():
    out = completed_daily_bars(_df("2026-11-23 05:00:00+00:00"), MON_10AM_ET)
    assert out.empty
    assert history_age_days(out, MON_10AM_ET) is None
    assert not is_history_fresh(out, MON_10AM_ET)


def test_friday_bar_is_fresh_on_monday():
    df = _df("2026-11-20 05:00:00+00:00")
    assert history_age_days(df, MON_10AM_ET) == 3
    assert is_history_fresh(df, MON_10AM_ET)


def test_ten_month_old_history_is_not_fresh():
    df = _df("2026-01-02 05:00:00+00:00")
    assert not is_history_fresh(df, MON_10AM_ET)