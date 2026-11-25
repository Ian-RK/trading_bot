"""Shadow-mode news log: stamp headlines with OUR first_seen_at, score once a day.

Log-only. No order path. No network: `fetch` and `score` are injected.
Day D's headlines are those first seen after the previous weekday's 16:00 ET
cutoff and at or before D's cutoff. Alpaca's created_at is stored for
reference and used only to DROP items that were already stale when first seen.
"""
import json
import os
from datetime import datetime, timedelta, timezone

from utils.ai_compare import ET, decision_cutoff
from utils.ai_sentiment import headlines_available

POLL_SECONDS = 300
MAX_AGE_AT_FIRST_SEEN = timedelta(hours=24)
MAX_HEADLINE_CHARS = 500
MAX_ITEMS = 30


def _require_aware(dt):
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise ValueError("time must be a timezone-aware datetime")
    return dt


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def _parse(s):
    try:
        dt = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else None


def _created_iso(v):
    if isinstance(v, datetime):
        return _iso(v) if v.tzinfo is not None else None
    dt = _parse(v)
    return _iso(dt) if dt is not None else None


def _prev_weekday(d):
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def day_due(now, scored_days):
    """ET date to score now, or None (weekend, before 16:00 ET, already done)."""
    _require_aware(now)
    day = now.astimezone(ET).date()
    if day.weekday() >= 5:
        return None
    if now < decision_cutoff(day):
        return None
    if day.isoformat() in scored_days:
        return None
    return day


class ShadowLog:
    def __init__(self, path):
        self.path = path
        self.items = []
        self.scored_days = set()
        self.bad_lines = 0
        self._seen = set()
        self._last_poll = None
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    self.bad_lines += 1
                    continue
                if not isinstance(rec, dict):
                    self.bad_lines += 1
                    continue
                kind = rec.get("kind")
                if (kind == "headline" and isinstance(rec.get("id"), str)
                        and isinstance(rec.get("headline"), str)
                        and _parse(rec.get("first_seen_at")) is not None):
                    self._seen.add(rec["id"])
                    self.items.append(rec)
                elif kind == "score" and isinstance(rec.get("day"), str):
                    self.scored_days.add(rec["day"])
                else:
                    self.bad_lines += 1

    def _append(self, rec):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def record_new(self, raw_items, now):
        """Stamp unseen items with `now` and append them. Returns the new count."""
        _require_aware(now)
        n = 0
        for raw in raw_items or []:
            if not isinstance(raw, dict):
                continue
            rid = raw.get("id")
            text = " ".join(str(raw.get("headline") or "").split())[:MAX_HEADLINE_CHARS]
            if rid is None or not str(rid).strip() or not text:
                continue
            rid = str(rid)
            if rid in self._seen:
                continue
            rec = {"kind": "headline", "id": rid, "headline": text,
                   "first_seen_at": _iso(now),
                   "alpaca_created_at": _created_iso(raw.get("created_at")),
                   "source": str(raw.get("source") or "")[:50]}
            self._append(rec)            # only remembered once safely written
            self._seen.add(rid)
            self.items.append(rec)
            n += 1
        return n

    def select_for_day(self, day):
        cutoff = decision_cutoff(day)
        lower = decision_cutoff(_prev_weekday(day))
        cands = []
        for rec in self.items:
            seen = _parse(rec["first_seen_at"])
            if seen is None or not seen > lower:
                continue
            created = _parse(rec.get("alpaca_created_at"))
            if created is not None and seen - created > MAX_AGE_AT_FIRST_SEEN:
                continue
            cands.append({"id": rec["id"], "headline": rec["headline"],
                          "first_seen_at": seen})
        return headlines_available(cands, cutoff, MAX_ITEMS)

    def score_day(self, day, now, score):
        heads = self.select_for_day(day)
        try:
            res = score(day.isoformat(), heads)
        except Exception as e:
            res = {"ok": False, "reason": f"scorer raised ({type(e).__name__})",
                   "source": "none"}
        if not isinstance(res, dict):
            res = {}
        rec = {"kind": "score", "day": day.isoformat(), "scored_at": _iso(now),
               "n_headlines": len(heads), "score": res.get("score"),
               "confidence": res.get("confidence"), "ok": bool(res.get("ok")),
               "reason": str(res.get("reason", ""))[:200],
               "source": res.get("source")}
        self._append(rec)
        self.scored_days.add(rec["day"])
        return rec

    def step(self, now, fetch, score):
        """One shadow pass: poll if due, then score if due. Never raises."""
        out = {"polled": False, "new": 0, "scored_day": None, "errors": []}
        try:
            _require_aware(now)
            due = (self._last_poll is None or
                   (now - self._last_poll).total_seconds() >= POLL_SECONDS)
            if due:
                self._last_poll = now
                out["polled"] = True
                try:
                    out["new"] = self.record_new(fetch(), now)
                except Exception as e:
                    out["errors"].append(f"poll failed ({type(e).__name__})")
            day = day_due(now, self.scored_days)
            if day is not None:
                out["scored_day"] = self.score_day(day, now, score)["day"]
        except Exception as e:
            out["errors"].append(f"shadow step failed ({type(e).__name__})")
        return out