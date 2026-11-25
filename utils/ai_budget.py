"""Request budget and score cache for the advisory AI layer.

Local JSON files only: no network. The budget is counted BEFORE a call is
made (failed calls may count against the provider's limit too) and fails
closed: if the budget file is unreadable, no calls are allowed.
"""
import copy
import json
import os
import re
import tempfile

import pandas as pd

DEFAULT_DAILY_LIMIT = 40     # below the assumed (unverified) provider limit of 50
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utc_day(now):
    ts = pd.Timestamp(now)
    if ts.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return ts.tz_convert("UTC").strftime("%Y-%m-%d")


def _atomic_write(path, obj):
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


class RequestBudget:
    """Persistent per-UTC-day request counter."""

    def __init__(self, path, daily_limit=DEFAULT_DAILY_LIMIT):
        self.path = path
        self.daily_limit = daily_limit

    def _count_today(self, day):
        if not os.path.exists(self.path):
            return 0
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("day"), str):
            raise ValueError("bad budget file")
        if data["day"] > day:
            raise ValueError("budget file is dated in the future")
        if data["day"] < day:
            return 0
        n = data.get("count")
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("bad budget count")
        return n

    def try_consume(self, now):
        """Reserve one request. True means the caller may make the call."""
        day = _utc_day(now)
        try:
            n = self._count_today(day)
        except (OSError, ValueError):
            return False
        if n >= self.daily_limit:
            return False
        try:
            _atomic_write(self.path, {"day": day, "count": n + 1})
        except OSError:
            return False
        return True


class ScoreCache:
    """Disk cache of validated scores, keyed by model, prompt version and day."""

    def __init__(self, path):
        self.path = path

    @staticmethod
    def _key(model, prompt_version, day):
        if not isinstance(day, str) or not _DAY.match(day):
            raise ValueError("day must be YYYY-MM-DD")
        return "|".join([str(model), str(prompt_version), day])

    def _read(self):
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("bad cache file")
        return data

    def get(self, model, prompt_version, day):
        key = self._key(model, prompt_version, day)
        try:
            entry = self._read().get(key)
        except (OSError, ValueError):
            return None
        if not isinstance(entry, dict) or not isinstance(entry.get("result"), dict):
            return None
        return copy.deepcopy(entry["result"])

    def put(self, model, prompt_version, day, result, meta=None):
        """Store a VALID result only. Refuses to overwrite a corrupt cache file."""
        key = self._key(model, prompt_version, day)
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise ValueError("only successful results are cached")
        data = self._read()          # raises ValueError if corrupt
        data[key] = {"result": result, "meta": meta or {}}
        _atomic_write(self.path, data)