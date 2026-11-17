"""
Filename: data_freshness.py
Description: Pure freshness check for a market-data bar. Fail-closed.
"""

from datetime import datetime


def check_bar_freshness(bar_time, now, max_age_seconds=180, max_future_seconds=5):
    """
    Returns (ok: bool, reason: str, age_seconds: float | None).
    bar_time and now must be timezone-aware datetimes.
    """
    if not isinstance(bar_time, datetime) or bar_time.tzinfo is None:
        return False, "bar timestamp missing or timezone-naive", None
    if not isinstance(now, datetime) or now.tzinfo is None:
        return False, "now must be a timezone-aware datetime", None

    age = (now - bar_time).total_seconds()

    if age < -max_future_seconds:
        return False, f"bar timestamp is {-age:.0f}s in the future (clock problem?)", age
    if age > max_age_seconds:
        return False, f"bar is {age:.0f}s old (limit {max_age_seconds}s)", age
    return True, "OK", age