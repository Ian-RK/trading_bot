from datetime import datetime, timedelta, timezone

from utils.data_freshness import check_bar_freshness

NOW = datetime(2026, 11, 16, 15, 0, 0, tzinfo=timezone.utc)


def ago(seconds):
    return NOW - timedelta(seconds=seconds)


def test_fresh_bar_passes():
    ok, reason, age = check_bar_freshness(ago(90), NOW)
    assert ok and reason == "OK" and age == 90

def test_exactly_at_limit_passes():
    assert check_bar_freshness(ago(180), NOW)[0] is True

def test_just_over_limit_fails():
    ok, reason, _ = check_bar_freshness(ago(181), NOW)
    assert not ok and "old" in reason

def test_very_old_bar_fails():
    assert check_bar_freshness(ago(86_400), NOW)[0] is False

def test_slightly_future_bar_is_tolerated():
    assert check_bar_freshness(ago(-3), NOW)[0] is True

def test_far_future_bar_fails():
    ok, reason, _ = check_bar_freshness(ago(-60), NOW)
    assert not ok and "future" in reason

def test_naive_bar_time_fails():
    assert check_bar_freshness(datetime(2026, 11, 16, 14, 59), NOW)[0] is False

def test_naive_now_fails():
    assert check_bar_freshness(ago(10), datetime(2026, 11, 16, 15, 0))[0] is False

def test_none_bar_time_fails():
    assert check_bar_freshness(None, NOW)[0] is False

def test_string_bar_time_fails():
    assert check_bar_freshness("2026-11-16T14:58:00Z", NOW)[0] is False

def test_custom_limit():
    assert check_bar_freshness(ago(250), NOW, max_age_seconds=300)[0] is True
    assert check_bar_freshness(ago(250), NOW, max_age_seconds=200)[0] is False

def test_other_timezone_is_handled():
    est = timezone(timedelta(hours=-5))
    assert check_bar_freshness(ago(60).astimezone(est), NOW)[0] is True