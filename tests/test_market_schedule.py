from datetime import date, datetime, timezone
from types import SimpleNamespace

from utils.market_schedule import classify_market_time


def utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def session(d, open_t=(9, 30), close_t=(16, 0)):
    return SimpleNamespace(
        date=d,
        open=datetime(d.year, d.month, d.day, *open_t),
        close=datetime(d.year, d.month, d.day, *close_t),
    )


FRI = date(2026, 11, 13)   # winter: Eastern = UTC-5
JUL = date(2026, 7, 15)    # summer: Eastern = UTC-4
HALF = date(2026, 11, 27)  # early close at 13:00
CAL = [session(FRI)]


def state(now, is_open=False, cal=CAL, **kw):
    return classify_market_time(now, is_open, cal, **kw)["state"]


# --- open ---
def test_open_clock_means_open():
    assert state(utc(2026, 11, 13, 16, 0), is_open=True) == "OPEN"

def test_open_even_with_empty_calendar():
    assert state(utc(2026, 11, 13, 16, 0), is_open=True, cal=[]) == "OPEN"

# --- warm-up (winter) ---
def test_warmup_inside_buffer():
    assert state(utc(2026, 11, 13, 14, 28)) == "WARMUP"      # 9:28 ET

def test_warmup_starts_at_buffer_edge():
    assert state(utc(2026, 11, 13, 14, 27)) == "WARMUP"      # 9:27 ET

def test_before_buffer_is_closed():
    assert state(utc(2026, 11, 13, 14, 26)) == "CLOSED"

# --- in-session but clock closed ---
def test_clock_closed_during_session_is_unknown():
    assert state(utc(2026, 11, 13, 15, 0)) == "UNKNOWN"      # 10:00 ET

# --- cool-down ---
def test_cooldown_starts_at_close():
    assert state(utc(2026, 11, 13, 21, 0)) == "COOLDOWN"     # 16:00 ET

def test_cooldown_inside_window():
    assert state(utc(2026, 11, 13, 21, 10)) == "COOLDOWN"

def test_cooldown_ends_at_window_edge():
    assert state(utc(2026, 11, 13, 21, 20)) == "CLOSED"

# --- the UTC-date bug: 8 PM Eastern is already "tomorrow" in UTC ---
def test_evening_eastern_is_closed_with_eastern_date_entry():
    assert state(utc(2026, 11, 14, 1, 0)) == "CLOSED"        # 20:00 ET Fri

def test_calendar_entry_for_utc_date_is_rejected():
    assert state(utc(2026, 11, 14, 1, 0), cal=[session(date(2026, 11, 14))]) == "UNKNOWN"

# --- daylight saving ---
def test_summer_warmup_uses_utc_minus_4():
    assert state(utc(2026, 7, 15, 13, 28), cal=[session(JUL)]) == "WARMUP"   # 9:28 EDT

def test_summer_before_buffer_is_closed():
    assert state(utc(2026, 7, 15, 13, 25), cal=[session(JUL)]) == "CLOSED"

# --- early close ---
def test_early_close_cooldown():
    cal = [session(HALF, close_t=(13, 0))]
    assert state(utc(2026, 11, 27, 18, 5), cal=cal) == "COOLDOWN"            # 13:05 ET

def test_early_close_afternoon_is_closed():
    cal = [session(HALF, close_t=(13, 0))]
    assert state(utc(2026, 11, 27, 19, 0), cal=cal) == "CLOSED"              # 14:00 ET

# --- weekends and holidays ---
def test_empty_calendar_is_closed():
    assert state(utc(2026, 11, 14, 15, 0), cal=[]) == "CLOSED"

# --- bad inputs fail closed ---
def test_none_calendar_is_unknown():
    assert state(utc(2026, 11, 13, 21, 5), cal=None) == "UNKNOWN"

def test_none_is_open_is_unknown():
    assert state(utc(2026, 11, 13, 21, 5), is_open=None) == "UNKNOWN"

def test_string_is_open_is_unknown():
    assert state(utc(2026, 11, 13, 21, 5), is_open="True") == "UNKNOWN"

def test_naive_now_is_unknown():
    assert state(datetime(2026, 11, 13, 21, 5)) == "UNKNOWN"

def test_two_entries_is_unknown():
    assert state(utc(2026, 11, 13, 21, 5), cal=[session(FRI), session(FRI)]) == "UNKNOWN"

def test_entry_missing_fields_is_unknown():
    assert state(utc(2026, 11, 13, 21, 5), cal=[SimpleNamespace(date=FRI)]) == "UNKNOWN"

def test_close_before_open_is_unknown():
    cal = [session(FRI, open_t=(16, 0), close_t=(9, 30))]
    assert state(utc(2026, 11, 13, 21, 5), cal=cal) == "UNKNOWN"

# --- custom windows ---
def test_custom_buffer():
    assert state(utc(2026, 11, 13, 14, 21), buffer_minutes=10) == "WARMUP"   # 9:21 ET

def test_zero_exit_window_means_no_cooldown():
    assert state(utc(2026, 11, 13, 21, 0), exit_window_minutes=0) == "CLOSED"