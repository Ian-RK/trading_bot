import requests

import utils.tele_monitor as tm

FAKE_TOKEN = "SECRET123TOKEN"


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Client Error for url: "
                f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage",
                response=self,
            )

    def json(self):
        if self._body is None:
            raise ValueError("no json body")
        return self._body


def setup(monkeypatch, post):
    monkeypatch.setattr(tm, "TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(tm, "CHAT_ID", "12345")
    monkeypatch.setattr(tm.requests, "post", post)


def test_success_returns_true(monkeypatch, capsys):
    setup(monkeypatch, lambda *a, **k: FakeResponse(200))
    assert tm.send_telegram_message("hi") is True
    assert capsys.readouterr().out == ""


def test_connection_error_does_not_leak_token(monkeypatch, capsys):
    def post(*a, **k):
        raise requests.exceptions.ConnectionError(
            f"Max retries exceeded with url: /bot{FAKE_TOKEN}/sendMessage")
    setup(monkeypatch, post)
    assert tm.send_telegram_message("hi") is False
    out = capsys.readouterr().out
    assert FAKE_TOKEN not in out
    assert "ConnectionError" in out


def test_http_error_shows_status_but_not_token(monkeypatch, capsys):
    body = {"description": "Bad Request: can't parse entities"}
    setup(monkeypatch, lambda *a, **k: FakeResponse(400, body))
    assert tm.send_telegram_message("hi") is False
    out = capsys.readouterr().out
    assert "HTTP 400" in out
    assert "can't parse entities" in out
    assert FAKE_TOKEN not in out


def test_token_inside_description_is_redacted(monkeypatch, capsys):
    body = {"description": f"bad token {FAKE_TOKEN} rejected"}
    setup(monkeypatch, lambda *a, **k: FakeResponse(401, body))
    assert tm.send_telegram_message("hi") is False
    out = capsys.readouterr().out
    assert FAKE_TOKEN not in out
    assert "<redacted>" in out


def test_http_error_without_json_body(monkeypatch, capsys):
    setup(monkeypatch, lambda *a, **k: FakeResponse(502, None))
    assert tm.send_telegram_message("hi") is False
    out = capsys.readouterr().out
    assert "HTTP 502" in out
    assert FAKE_TOKEN not in out


def test_missing_credentials_skips_without_posting(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(tm, "TOKEN", None)
    monkeypatch.setattr(tm, "CHAT_ID", None)
    monkeypatch.setattr(tm.requests, "post", lambda *a, **k: called.append(1))
    assert tm.send_telegram_message("hi") is False
    assert called == []
    assert "credentials missing" in capsys.readouterr().out