"""
Filename: market_schedule.py
Description: Pure function that classifies "what time is it, market-wise".
    No API calls. Fail-closed: bad or inconsistent data -> UNKNOWN.
    Alpaca calendar open/close are NAIVE datetimes in US Eastern time.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _result(state, reason):
    return {"state": state, "reason": reason}


def _as_eastern(dt):
    if not isinstance(dt, datetime):
        raise TypeError(f"not a datetime: {dt!r}")
    return dt.replace(tzinfo=ET) if dt.tzinfo is None else dt.astimezone(ET)


def classify_market_time(now, is_open, calendar,
                         buffer_minutes=3, exit_window_minutes=20):
    """
    now:      timezone-aware datetime
    is_open:  bool from the broker clock
    calendar: list of calendar entries for TODAY'S EASTERN DATE
              (each with .date, .open, .close)
    """
    if not isinstance(now, datetime) or now.tzinfo is None:
        return _result("UNKNOWN", "now must be a timezone-aware datetime")

    if not isinstance(is_open, bool):
        return _result("UNKNOWN", f"invalid is_open: {is_open!r}")

    if is_open:
        return _result("OPEN", "broker clock says the market is open")

    if not isinstance(calendar, (list, tuple)):
        return _result("UNKNOWN", "calendar is not a list")

    if len(calendar) == 0:
        return _result("CLOSED", "no trading session today (weekend/holiday)")

    if len(calendar) != 1:
        return _result("UNKNOWN", f"expected 1 calendar entry, got {len(calendar)}")

    entry = calendar[0]
    try:
        session_date = entry.date
        open_dt = _as_eastern(entry.open)
        close_dt = _as_eastern(entry.close)
    except Exception as e:
        return _result("UNKNOWN", f"bad calendar entry: {e}")

    if session_date != now.astimezone(ET).date():
        return _result("UNKNOWN", "calendar entry is not for today's Eastern date")

    if close_dt <= open_dt:
        return _result("UNKNOWN", "calendar close is not after open")

    if open_dt - timedelta(minutes=buffer_minutes) <= now < open_dt:
        return _result("WARMUP", "inside the pre-open buffer")

    if open_dt <= now < close_dt:
        return _result("UNKNOWN",
                       "calendar says in-session but broker clock says closed")

    if close_dt <= now < close_dt + timedelta(minutes=exit_window_minutes):
        return _result("COOLDOWN", "inside the post-close window")

    return _result("CLOSED", "outside all trading windows")