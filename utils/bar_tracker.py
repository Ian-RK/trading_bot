"""
Filename: bar_tracker.py
Description: Remembers the timestamp of the last fully processed bar so the
    same bar is never processed twice. In-memory only. Fail-closed:
    a missing or timezone-naive timestamp is never "new".
"""

from datetime import datetime


def _valid(ts):
    return isinstance(ts, datetime) and ts.tzinfo is not None


class BarTracker:
    def __init__(self):
        self.last_processed = None

    def is_new(self, bar_time):
        if not _valid(bar_time):
            return False
        if self.last_processed is None:
            return True
        return bar_time > self.last_processed

    def mark_processed(self, bar_time):
        if not _valid(bar_time):
            raise ValueError(f"cannot mark invalid bar time: {bar_time!r}")
        if self.last_processed is None or bar_time > self.last_processed:
            self.last_processed = bar_time