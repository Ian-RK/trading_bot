from datetime import datetime, timezone
from types import SimpleNamespace

from utils.shadow_log import ShadowLog
from utils.shadow_runner import fetch_news_items, make_scorer, shadow_tick

UTC = timezone.utc


class FakeClient:
    def __init__(self, res):
        self.res, self.req = res, None

    def get_news(self, req):
        self.req = req
        return self.res


def test_fetch_news_items_from_newsset_shape():
    created = datetime(2026, 11, 18, 14, 0, tzinfo=UTC)
    n = SimpleNamespace(id=7, headline="H", created_at=created, source="s")
    client = FakeClient(SimpleNamespace(data={"news": [n]}))
    out = fetch_news_items(client)
    assert out == [{"id": 7, "headline": "H", "created_at": created, "source": "s"}]
    assert client.req.limit == 50 and client.req.sort == "desc"


def test_fetch_news_items_accepts_plain_list_of_dicts():
    client = FakeClient([{"id": 1, "headline": "x", "created_at": None, "source": "s"}])
    assert fetch_news_items(client)[0]["id"] == 1
    assert fetch_news_items(FakeClient(None)) == []


class Resp:
    status_code = 200

    def json(self):
        return {"choices": [{"message": {
            "content": '{"score": 0.5, "confidence": 0.8}'}}]}


def test_make_scorer_calls_api_once_then_cache(tmp_path):
    calls = []

    def post(url, headers, payload, timeout):
        calls.append(1)
        return Resp()

    score = make_scorer(str(tmp_path / "b.json"), str(tmp_path / "c.json"),
                        post=post, api_key="test-key")
    first = score("2026-11-18", [{"headline": "Fed holds rates"}])
    assert first["ok"] is True and first["source"] == "api" and first["score"] == 0.5
    second = score("2026-11-18", [{"headline": "Fed holds rates"}])
    assert second["source"] == "cache" and len(calls) == 1


def test_shadow_tick_audits_only_when_something_happened(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))
    events = []
    audit = lambda name, **kw: events.append((name, kw))
    now = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)          # before the cutoff
    fetch = lambda: [{"id": "1", "headline": "h", "created_at": None}]
    shadow_tick(log, now, fetch, lambda d, h: {}, audit)
    assert events == [("shadow", {"new": 1, "scored_day": None, "errors": []})]
    shadow_tick(log, now, fetch, lambda d, h: {}, audit)      # poll not due again
    assert len(events) == 1


def test_shadow_tick_swallows_audit_failure(tmp_path):
    log = ShadowLog(str(tmp_path / "s.jsonl"))

    def bad_audit(name, **kw):
        raise OSError("disk full")

    now = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
    shadow_tick(log, now, lambda: [{"id": "1", "headline": "h"}],
                lambda d, h: {}, bad_audit)                   # must not raise