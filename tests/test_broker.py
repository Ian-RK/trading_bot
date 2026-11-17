from types import SimpleNamespace

from utils.broker import check_paper_only

PAPER_URL = "https://paper-api.alpaca.markets"


class FakeClient:
    def __init__(self, number="PA123456", error=None):
        self.number = number
        self.error = error
        self.calls = 0

    def get_account(self):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(account_number=self.number)


def test_paper_account_with_paper_url_is_ok():
    assert check_paper_only(FakeClient(), PAPER_URL) == (True, "OK")

def test_unset_url_is_ok_when_account_is_paper():
    assert check_paper_only(FakeClient(), None)[0] is True

def test_blank_url_is_ok_when_account_is_paper():
    assert check_paper_only(FakeClient(), "   ")[0] is True

def test_paper_url_with_path_and_slash_is_ok():
    assert check_paper_only(FakeClient(), PAPER_URL + "/v2/")[0] is True

def test_live_url_is_blocked():
    ok, reason = check_paper_only(FakeClient(), "https://api.alpaca.markets")
    assert not ok and "BASE_URL" in reason

def test_lookalike_host_is_blocked():
    assert check_paper_only(FakeClient(), PAPER_URL + ".evil.com")[0] is False

def test_bad_url_never_queries_the_broker():
    client = FakeClient()
    check_paper_only(client, "https://api.alpaca.markets")
    assert client.calls == 0

def test_non_paper_account_number_is_blocked():
    ok, reason = check_paper_only(FakeClient(number="AB123456"), PAPER_URL)
    assert not ok and "paper" in reason

def test_missing_account_number_is_blocked():
    assert check_paper_only(FakeClient(number=None), PAPER_URL)[0] is False

def test_query_error_is_blocked():
    ok, reason = check_paper_only(FakeClient(error=RuntimeError("unauthorized")), PAPER_URL)
    assert not ok and "query failed" in reason