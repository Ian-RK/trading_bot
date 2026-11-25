import json
from datetime import date, datetime, timedelta, timezone

import pytest

from utils.shadow_log import ShadowLog

UTC = timezone.utc


def t(day, h, m=0, s=0):
    """Nov 2026 in UTC. EST all month, so 16:00 ET = 21:00 UTC."""
    return datetime(2026, 11, day, h, m, s, tzinfo=UTC)


def raw(i, created=None):
    return {"id": str(i), "headline": f"headline {i}", "created_at": created}


def ids(heads):
    return [h["id"] for h in heads]


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def test_record_new_stamps_and_dedupes(tmp_path):
    p = str(tmp_path / "s.jsonl")
    log = ShadowLog(p)
    assert log.record_new([raw(1), raw(2)], t(18, 15)) == 2
    assert log.record_new([raw(1), raw(3)], t(18, 16)) == 1
    seen = {r["id"]: r["first_seen_at"] for r in read(p)}
    assert seen == {"1": t(18, 15).isoformat(), "2": t(18, 15).isoformat(),
                    "3": t(18, 16).isoformat()}


def test_bad_items_skipped(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    bad = [None, "x", {"headline": "no id"}, {"id": "9"}, {"id": " ", "headline": "h"},
           {"id": "10", "headline": "   "}]
    assert log.record_new(bad, t(18, 15)) == 0
    assert log.items == []


def test_naive_now_raises(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    with pytest.raises(ValueError):
        log.record_new([raw(1)], datetime(2026, 11, 18, 15, 0))


def test_persistence_across_restart(tmp_path):
    p = str(tmp_path / "s.jsonl")
    log = ShadowLog(p)
    log.record_new([raw(1)], t(18, 15))
    again = ShadowLog(p)
    assert again.record_new([raw(1)], t(18, 20)) == 0
    assert ids(again.select_for_day(date(2026, 11, 18))) == ["1"]
    assert again.items[0]["first_seen_at"] == t(18, 15).isoformat()


def test_corrupt_lines_skipped_and_preserved(tmp_path):
    p = tmp_path / "s.jsonl"
    good = json.dumps({"kind": "headline", "id": "1", "headline": "h",
                       "first_seen_at": t(18, 15).isoformat()})
    p.write_text("garbage\n" + good + "\n", encoding="utf-8")
    log = ShadowLog(str(p))
    assert log.bad_lines == 1
    assert len(log.items) == 1
    log.record_new([raw(2)], t(18, 16))
    assert p.read_text(encoding="utf-8").startswith("garbage\n")


def test_window_edges_for_a_midweek_day(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    log.record_new([raw("A")], t(17, 20, 59))        # before Tue cutoff: belongs to Tue
    log.record_new([raw("B")], t(17, 21, 1))
    log.record_new([raw("C")], t(18, 21, 0, 0))      # exactly the cutoff: included
    log.record_new([raw("D")], t(18, 21, 0, 1))      # after the cutoff: excluded
    assert ids(log.select_for_day(date(2026, 11, 18))) == ["B", "C"]


def test_monday_window_includes_weekend(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    log.record_new([raw("F0")], t(20, 20, 59))       # Friday, before Fri cutoff
    log.record_new([raw("F1")], t(20, 21, 1))
    log.record_new([raw("S")], t(21, 12))
    log.record_new([raw("U")], t(22, 12))
    log.record_new([raw("M")], t(23, 15))
    assert ids(log.select_for_day(date(2026, 11, 23))) == ["F1", "S", "U", "M"]


def test_stale_at_first_sight_is_dropped(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    now = t(18, 15)
    log.record_new([raw("old", created=(now - timedelta(hours=30)).isoformat()),
                    raw("fresh", created=(now - timedelta(hours=2)).isoformat()),
                    raw("nots", created=None)], now)
    assert ids(log.select_for_day(date(2026, 11, 18))) == ["fresh", "nots"]


def test_only_newest_30_kept_oldest_first(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    for i in range(35):
        log.record_new([raw(i)], t(18, 10, i))
    got = ids(log.select_for_day(date(2026, 11, 18)))
    assert got == [str(i) for i in range(5, 35)]


def test_scores_once_after_cutoff_not_before(tmp_path):
    p = str(tmp_path / "s.jsonl")
    log = ShadowLog(p)
    calls = []

    def score(day, heads):
        calls.append((day, ids(heads)))
        return {"score": 0.4, "confidence": 0.8, "ok": True, "reason": "", "source": "api"}

    fetch = lambda: [raw(1)]
    assert log.step(t(18, 20, 59), fetch, score)["scored_day"] is None
    assert calls == []
    out = log.step(t(18, 21, 0), fetch, score)           # cutoff is inclusive
    assert out["scored_day"] == "2026-11-18"
    assert calls == [("2026-11-18", ["1"])]
    log.step(t(18, 21, 30), fetch, score)
    assert len(calls) == 1
    scores = [r for r in read(p) if r["kind"] == "score"]
    assert len(scores) == 1 and scores[0]["n_headlines"] == 1 and scores[0]["score"] == 0.4


def test_late_headline_is_not_scored_for_that_day(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    seen = []
    feeds = iter([[raw(1)], [raw(1), raw(2)]])
    score = lambda day, heads: seen.append(ids(heads)) or {"ok": True, "score": 0.0,
                                                           "confidence": 0.9}
    log.step(t(18, 20, 0), lambda: next(feeds), score)
    log.step(t(18, 21, 1), lambda: next(feeds), score)   # item 2 first seen after cutoff
    assert seen == [["1"]]
    assert ids(log.select_for_day(date(2026, 11, 19))) == ["2"]


def test_weekend_is_not_scored(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    calls = []
    out = log.step(t(21, 22), lambda: [raw(1)], lambda d, h: calls.append(d) or {})
    assert out["scored_day"] is None and calls == []


def test_poll_interval(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    n = []
    fetch = lambda: n.append(1) or []
    log.step(t(18, 10, 0, 0), fetch, lambda d, h: {})
    log.step(t(18, 10, 4, 59), fetch, lambda d, h: {})
    assert len(n) == 1
    log.step(t(18, 10, 5, 0), fetch, lambda d, h: {})
    assert len(n) == 2


def test_step_never_raises_on_fetch_or_score_error(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    calls = []

    def boom_fetch():
        raise RuntimeError("net down")

    def boom_score(day, heads):
        calls.append(day)
        raise RuntimeError("scorer down")

    out = log.step(t(18, 21, 5), boom_fetch, boom_score)
    assert out["errors"] == ["poll failed (RuntimeError)"]
    assert out["scored_day"] == "2026-11-18"
    assert "RuntimeError" in read(log.path)[-1]["reason"]
    assert read(log.path)[-1]["ok"] is False
    log.step(t(18, 22, 0), boom_fetch, boom_score)       # no retry the same day
    assert calls == ["2026-11-18"]


def test_step_with_naive_time_does_not_raise(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    out = log.step(datetime(2026, 11, 18, 12, 0), lambda: [], lambda d, h: {})
    assert out["errors"] and out["scored_day"] is None


def test_scored_day_survives_restart(tmp_path):
    p = str(tmp_path / "s.jsonl")
    ShadowLog(p).step(t(18, 21, 5), lambda: [raw(1)], lambda d, h: {"ok": True})
    calls = []
    out = ShadowLog(p).step(t(18, 22), lambda: [], lambda d, h: calls.append(d) or {})
    assert out["scored_day"] is None and calls == []