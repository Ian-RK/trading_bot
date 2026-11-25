from datetime import datetime, timezone

import pytest

from utils.ai_budget import RequestBudget, ScoreCache
from utils.ai_client import (MODEL, PROMPT_VERSION, TIMEOUT_SECONDS, URL,
                             get_daily_score)

NOW = datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc)
DAY = "2026-11-25"
OK = {"score": 0.1, "confidence": 0.5, "ok": True, "reason": ""}
HEADS = [{"headline": "Fed holds rates steady"}]
GOOD = '{"score": -0.3, "confidence": 0.6}'


class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _ok_body(text):
    return {"choices": [{"message": {"content": text}}]}


class _Post:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.calls = resp, exc, []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload, timeout))
        if self.exc:
            raise self.exc
        return self.resp


def _setup(tmp_path, limit=5):
    return (RequestBudget(tmp_path / "b.json", daily_limit=limit),
            ScoreCache(tmp_path / "c.json"))


def test_cache_hit_makes_no_call_and_uses_no_budget(tmp_path):
    budget, cache = _setup(tmp_path)
    cache.put(MODEL, PROMPT_VERSION, DAY, OK)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    r = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert r["score"] == 0.1 and r["source"] == "cache"
    assert post.calls == []
    assert not (tmp_path / "b.json").exists()


def test_no_headlines_makes_no_call(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    for heads in ([], [{"headline": "   "}]):
        r = get_daily_score(DAY, heads, NOW, budget, cache, post=post, api_key="k")
        assert r["ok"] is False and r["score"] == 0.0
    assert post.calls == []


def test_missing_key_makes_no_call_and_uses_no_budget(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    r = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post)
    assert r["ok"] is False
    assert post.calls == []
    assert not (tmp_path / "b.json").exists()


def test_exhausted_budget_makes_no_call(tmp_path):
    budget, cache = _setup(tmp_path, limit=0)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    r = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert r["ok"] is False and "budget" in r["reason"]
    assert post.calls == []


def test_success_is_cached_and_second_call_uses_cache(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    r1 = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert r1["ok"] and r1["score"] == -0.3 and r1["source"] == "api"
    r2 = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert r2["score"] == -0.3 and r2["source"] == "cache"
    assert len(post.calls) == 1


def test_http_error_is_neutral_and_not_cached(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(429, {"error": "rate limited"}))
    r = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert r["ok"] is False and "429" in r["reason"]
    get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert len(post.calls) == 2          # nothing was cached


def test_network_exception_is_neutral_and_does_not_leak_key(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(exc=RuntimeError("boom secret-key-123"))
    r = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post,
                        api_key="secret-key-123")
    assert r["ok"] is False and "RuntimeError" in r["reason"]
    assert "secret-key-123" not in str(r)


def test_bad_reply_is_neutral_and_not_cached(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(200, _ok_body("I think the market will go up")))
    r = get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="k")
    assert r["ok"] is False and r["score"] == 0.0
    assert cache.get(MODEL, PROMPT_VERSION, DAY) is None


@pytest.mark.parametrize("resp", [
    _Resp(200, {}),
    _Resp(200, {"choices": []}),
    _Resp(200, {"choices": [{"message": {"content": None}}]}),
    _Resp(200, []),
    _Resp(200, None),
])
def test_malformed_response_shapes_are_neutral(tmp_path, resp):
    budget, cache = _setup(tmp_path)
    r = get_daily_score(DAY, HEADS, NOW, budget, cache,
                        post=_Post(resp), api_key="k")
    assert r["ok"] is False and r["score"] == 0.0


def test_request_shape(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    get_daily_score(DAY, HEADS, NOW, budget, cache, post=post, api_key="test-key")
    url, headers, payload, timeout = post.calls[0]
    assert url == URL and timeout == TIMEOUT_SECONDS
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["model"] == MODEL and payload["temperature"] == 0
    assert payload["messages"][0]["role"] == "system"
    assert "Fed holds rates steady" in payload["messages"][1]["content"]
    assert "test-key" not in str(payload)


def test_headlines_are_truncated_and_whitespace_collapsed(tmp_path):
    budget, cache = _setup(tmp_path)
    post = _Post(_Resp(200, _ok_body(GOOD)))
    heads = [{"headline": "A" * 500}, {"headline": "x   y\nz"}]
    get_daily_score(DAY, heads, NOW, budget, cache, post=post, api_key="k")
    content = post.calls[0][2]["messages"][1]["content"]
    assert "A" * 200 in content and "A" * 201 not in content
    assert "x y z" in content