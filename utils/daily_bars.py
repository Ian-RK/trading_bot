"""Helpers that keep only COMPLETED daily bars for the daily strategy.

Day boundaries use US Eastern time. A bar dated today (ET) is unfinished
while the market is open, so it is never handed to the strategy.
"""
import pandas as pd

ET = "America/New_York"
MAX_HISTORY_AGE_DAYS = 5   # covers a weekend plus a holiday


def _et_days(df):
    ts = pd.to_datetime(df["timestamp"], utc=True)
    return ts.dt.tz_convert(ET).dt.tz_localize(None).dt.normalize()


def _today_et(now):
    # `now` must be timezone-aware; a naive value raises TypeError on purpose.
    return pd.Timestamp(now).tz_convert(ET).tz_localize(None).normalize()


def completed_daily_bars(df, now):
    """Return a copy of df without rows dated today (ET) or later."""
    keep = _et_days(df) < _today_et(now)
    return df.loc[keep].reset_index(drop=True)


def history_age_days(df, now):
    """Calendar days from the newest bar to today (ET). None if df is empty."""
    if df.empty:
        return None
    return int((_today_et(now) - _et_days(df).max()).days)


def is_history_fresh(df, now, max_age_days=MAX_HISTORY_AGE_DAYS):
    age = history_age_days(df, now)
    return age is not None and age <= max_age_days