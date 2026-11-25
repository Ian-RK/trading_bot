"""Pure helpers for the advisory AI sentiment layer (no network, no files).

parse_sentiment: validate a model reply; any problem gives a neutral result.
headlines_available: point-in-time filter using OUR OWN first_seen_at stamps.
"""
import json
import math
import re

import pandas as pd

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def _neutral(reason):
    return {"score": 0.0, "confidence": 0.0, "ok": False, "reason": reason}


def _number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def parse_sentiment(text):
    """Expect JSON like {"score": -1..1, "confidence": 0..1}. Else neutral."""
    if not isinstance(text, str) or not text.strip():
        return _neutral("empty reply")
    body = text.strip()
    m = _FENCE.match(body)
    if m:
        body = m.group(1)
    try:
        obj = json.loads(body)
    except ValueError:
        return _neutral("not valid JSON")
    if not isinstance(obj, dict):
        return _neutral("JSON is not an object")
    score = _number(obj.get("score"))
    conf = _number(obj.get("confidence"))
    if score is None or conf is None:
        return _neutral("score/confidence missing or not numeric")
    if not (-1.0 <= score <= 1.0 and 0.0 <= conf <= 1.0):
        return _neutral("value out of range")
    return {"score": score, "confidence": conf, "ok": True, "reason": ""}


def _aware(x):
    ts = pd.Timestamp(x)
    if ts.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return ts


def headlines_available(items, cutoff, max_items=30):
    """Items first seen at or before cutoff, oldest first, newest max_items kept.

    Each item is a dict with a tz-aware "first_seen_at". Input is not mutated.
    """
    cutoff = _aware(cutoff)
    if max_items <= 0:
        return []
    keep = []
    for it in items:
        seen = _aware(it["first_seen_at"])
        if seen <= cutoff:
            keep.append((seen, it))
    keep.sort(key=lambda p: p[0])
    return [dict(it) for _, it in keep[-max_items:]]