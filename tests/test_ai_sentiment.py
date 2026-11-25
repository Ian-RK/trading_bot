import copy

import pytest

from utils.ai_sentiment import headlines_available, parse_sentiment

CUT = "2026-11-20 21:00:00+00:00"


def _h(text, ts):
    return {"headline": text, "first_seen_at": ts}


def test_valid_reply():
    r = parse_sentiment('{"score": -0.4, "confidence": 0.7}')
    assert r["ok"] and r["score"] == -0.4 and r["confidence"] == 0.7


def test_code_fence_is_accepted():
    r = parse_sentiment('```json\n{"score": 0.2, "confidence": 0.5}\n```')
    assert r["ok"] and r["score"] == 0.2


@pytest.mark.parametrize("bad", [
    "", None, "hello", "[1, 2]",
    '{"score": 2, "confidence": 0.5}',
    '{"score": 0.5}',
    '{"score": true, "confidence": 0.5}',
    '{"score": "0.5", "confidence": 0.5}',
    '{"score": NaN, "confidence": 0.5}',
    '{"score": 0.1, "confidence": -0.1}',
])
def test_bad_replies_give_neutral(bad):
    r = parse_sentiment(bad)
    assert r["ok"] is False and r["score"] == 0.0 and r["confidence"] == 0.0


def test_after_cutoff_excluded_and_cutoff_inclusive():
    items = [_h("early", "2026-11-20 20:00:00+00:00"),
             _h("exact", CUT),
             _h("late", "2026-11-20 21:00:01+00:00")]
    out = headlines_available(items, CUT)
    assert [i["headline"] for i in out] == ["early", "exact"]


def test_naive_cutoff_raises():
    with pytest.raises(ValueError):
        headlines_available([], "2026-11-20 21:00:00")


def test_naive_item_timestamp_raises():
    with pytest.raises(ValueError):
        headlines_available([_h("x", "2026-11-20 20:00:00")], CUT)


def test_cap_keeps_newest():
    items = [_h(str(n), f"2026-11-20 1{n}:00:00+00:00") for n in range(5)]
    out = headlines_available(items, CUT, max_items=2)
    assert [i["headline"] for i in out] == ["3", "4"]


def test_zero_cap_returns_nothing():
    assert headlines_available([_h("x", "2026-11-20 20:00:00+00:00")], CUT, max_items=0) == []


def test_input_not_mutated():
    items = [_h("b", "2026-11-20 20:00:00+00:00"), _h("a", "2026-11-20 19:00:00+00:00")]
    before = copy.deepcopy(items)
    headlines_available(items, CUT)
    assert items == before