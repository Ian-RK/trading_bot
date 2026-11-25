from datetime import datetime, timezone

import pytest

from utils.ai_budget import RequestBudget, ScoreCache

NOW = datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc)
NEXT_DAY = datetime(2026, 11, 26, 0, 1, tzinfo=timezone.utc)
OK = {"score": 0.1, "confidence": 0.5, "ok": True, "reason": ""}


def test_budget_stops_at_limit(tmp_path):
    b = RequestBudget(tmp_path / "b.json", daily_limit=3)
    assert [b.try_consume(NOW) for _ in range(5)] == [True, True, True, False, False]


def test_budget_persists_across_instances(tmp_path):
    p = tmp_path / "b.json"
    b1 = RequestBudget(p, daily_limit=3)
    b1.try_consume(NOW)
    b1.try_consume(NOW)
    b2 = RequestBudget(p, daily_limit=3)
    assert b2.try_consume(NOW) is True
    assert b2.try_consume(NOW) is False


def test_budget_resets_on_new_utc_day(tmp_path):
    b = RequestBudget(tmp_path / "b.json", daily_limit=1)
    assert b.try_consume(NOW) is True
    assert b.try_consume(NOW) is False
    assert b.try_consume(NEXT_DAY) is True


def test_corrupt_budget_file_fails_closed(tmp_path):
    p = tmp_path / "b.json"
    p.write_text("not json", encoding="utf-8")
    assert RequestBudget(p).try_consume(NOW) is False
    assert p.read_text(encoding="utf-8") == "not json"


def test_future_dated_budget_file_fails_closed(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('{"day": "2030-01-01", "count": 0}', encoding="utf-8")
    assert RequestBudget(p).try_consume(NOW) is False
    assert p.read_text(encoding="utf-8") == '{"day": "2030-01-01", "count": 0}'


def test_naive_now_raises(tmp_path):
    with pytest.raises(ValueError):
        RequestBudget(tmp_path / "b.json").try_consume(datetime(2026, 11, 25, 15, 0))


def test_cache_miss_returns_none(tmp_path):
    assert ScoreCache(tmp_path / "c.json").get("m", "v1", "2026-11-25") is None


def test_cache_round_trip_and_persistence(tmp_path):
    p = tmp_path / "c.json"
    ScoreCache(p).put("m", "v1", "2026-11-25", OK, meta={"n_headlines": 12})
    assert ScoreCache(p).get("m", "v1", "2026-11-25") == OK


def test_cache_key_separates_model_prompt_and_day(tmp_path):
    c = ScoreCache(tmp_path / "c.json")
    c.put("m", "v1", "2026-11-25", OK)
    assert c.get("other", "v1", "2026-11-25") is None
    assert c.get("m", "v2", "2026-11-25") is None
    assert c.get("m", "v1", "2026-11-26") is None


def test_cache_refuses_unsuccessful_result(tmp_path):
    p = tmp_path / "c.json"
    bad = {"score": 0.0, "confidence": 0.0, "ok": False, "reason": "x"}
    with pytest.raises(ValueError):
        ScoreCache(p).put("m", "v1", "2026-11-25", bad)
    assert not p.exists()


def test_corrupt_cache_is_a_miss_and_never_overwritten(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{{{", encoding="utf-8")
    c = ScoreCache(p)
    assert c.get("m", "v1", "2026-11-25") is None
    with pytest.raises(ValueError):
        c.put("m", "v1", "2026-11-25", OK)
    assert p.read_text(encoding="utf-8") == "{{{"


def test_cache_returns_a_copy(tmp_path):
    c = ScoreCache(tmp_path / "c.json")
    c.put("m", "v1", "2026-11-25", OK)
    c.get("m", "v1", "2026-11-25")["score"] = 0.99
    assert c.get("m", "v1", "2026-11-25")["score"] == 0.1


def test_bad_day_string_raises(tmp_path):
    with pytest.raises(ValueError):
        ScoreCache(tmp_path / "c.json").get("m", "v1", "11/25/2026")