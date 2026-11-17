from datetime import datetime, timedelta, timezone

import pytest

from utils.bar_tracker import BarTracker

T0 = datetime(2026, 11, 16, 15, 0, 0, tzinfo=timezone.utc)


def test_first_bar_is_new():
    assert BarTracker().is_new(T0) is True

def test_same_bar_after_processing_is_not_new():
    t = BarTracker()
    t.mark_processed(T0)
    assert t.is_new(T0) is False

def test_later_bar_is_new():
    t = BarTracker()
    t.mark_processed(T0)
    assert t.is_new(T0 + timedelta(minutes=1)) is True

def test_older_bar_is_not_new():
    t = BarTracker()
    t.mark_processed(T0)
    assert t.is_new(T0 - timedelta(minutes=1)) is False

def test_not_marked_means_still_new():
    t = BarTracker()
    assert t.is_new(T0) is True
    assert t.is_new(T0) is True          # checking alone does not consume it

def test_mark_never_moves_backwards():
    t = BarTracker()
    t.mark_processed(T0 + timedelta(minutes=5))
    t.mark_processed(T0)
    assert t.last_processed == T0 + timedelta(minutes=5)

@pytest.mark.parametrize("bad", [None, "2026-11-16T15:00:00Z", 12345,
                                 datetime(2026, 11, 16, 15, 0, 0)])
def test_invalid_time_is_never_new(bad):
    assert BarTracker().is_new(bad) is False

@pytest.mark.parametrize("bad", [None, "x", datetime(2026, 11, 16, 15, 0, 0)])
def test_marking_invalid_time_raises(bad):
    with pytest.raises(ValueError):
        BarTracker().mark_processed(bad)

def test_other_timezone_compares_correctly():
    est = timezone(timedelta(hours=-5))
    t = BarTracker()
    t.mark_processed(T0)
    assert t.is_new(T0.astimezone(est)) is False
    assert t.is_new((T0 + timedelta(minutes=1)).astimezone(est)) is True