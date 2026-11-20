from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from alpaca.trading.enums import OrderSide, TimeInForce

import utils.order_submit as sub

BAR = datetime(2026, 11, 17, 14, 35, tzinfo=timezone.utc)
CID = "tb1-SPY-buy-20261117T143500Z"
DEFAULT_INTENT = {"action": "BUY", "qty": 132, "reason": "test"}
OK_ORDERS = {"status": "OK", "count": 0}


class FakeClock:
    def __init__(self):
        self.t = 0.0
    def now(self):
        return self.t
    def sleep(self, seconds):
        self.t += seconds


class FakeAudit:
    def __init__(self):
        self.events = []
    def __call__(self, event, **fields):
        self.events.append((event, fields))


class FakeClient:
    def __init__(self, statuses=(("new", "0"),), submit_error=None,
                 lookup_error=None, order_qty="1"):
        self.statuses = list(statuses)
        self.submit_error = submit_error
        self.lookup_error = lookup_error
        self.order_qty = order_qty
        self.submitted = []
        self.lookups = 0

    def _order(self, status, filled):
        return SimpleNamespace(id="order-1", status=status,
                               qty=self.order_qty, filled_qty=filled)

    def submit_order(self, order_data):
        self.submitted.append(order_data)
        if self.submit_error:
            raise self.submit_error
        return self._order("new", "0")

    def get_order_by_client_id(self, client_order_id):
        self.lookups += 1
        if self.lookup_error:
            raise self.lookup_error
        status, filled = self.statuses[min(self.lookups - 1, len(self.statuses) - 1)]
        return self._order(status, filled)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("TRADING_ENABLED", raising=False)
    monkeypatch.setattr(sub, "DRY_RUN", True)
    sub.clear_unresolved_submission()
    yield
    sub.clear_unresolved_submission()


def go_live(monkeypatch):
    monkeypatch.setattr(sub, "DRY_RUN", False)
    monkeypatch.setenv("TRADING_ENABLED", "true")


def run(intent=DEFAULT_INTENT, client=None, ref_price=738.25, bar_time=BAR,
        equity=100_000.0, current_qty=0.0, open_orders=OK_ORDERS,
        halted=(False, "OK")):
    client = client if client is not None else FakeClient()
    clock = FakeClock()
    audit = FakeAudit()
    open_fn = open_orders if callable(open_orders) else (lambda: open_orders)
    result = sub.place_order(
        intent, "SPY", ref_price, bar_time, equity, current_qty,
        open_orders_fn=open_fn, client=client, halted_fn=lambda: halted,
        audit=audit, sleep=clock.sleep, clock=clock.now)
    return result, client, audit


# ---------- switches ----------
def test_dry_run_default_never_submits():
    result, client, _ = run()
    assert result["outcome"] == "DRY_RUN"
    assert client.submitted == [] and client.lookups == 0
    assert result["qty"] == 1                       # 132 cut to the $1,000 order cap
    assert result["limit_price"] == 738.99
    assert result["client_order_id"] == CID

def test_env_enabled_but_code_dry_run_still_dry(monkeypatch):
    monkeypatch.setenv("TRADING_ENABLED", "true")
    result, client, _ = run()
    assert result["outcome"] == "DRY_RUN" and client.submitted == []

def test_code_live_but_env_missing_is_dry(monkeypatch):
    monkeypatch.setattr(sub, "DRY_RUN", False)
    result, client, _ = run()
    assert result["outcome"] == "DRY_RUN" and client.submitted == []

@pytest.mark.parametrize("value", ["false", "", "0", "yes", "1", "no"])
def test_code_live_but_env_not_true_is_dry(monkeypatch, value):
    monkeypatch.setattr(sub, "DRY_RUN", False)
    monkeypatch.setenv("TRADING_ENABLED", value)
    result, client, _ = run()
    assert result["outcome"] == "DRY_RUN" and client.submitted == []

@pytest.mark.parametrize("value", ["true", "True", " TRUE "])
def test_trading_enabled_accepts_true(monkeypatch, value):
    monkeypatch.setenv("TRADING_ENABLED", value)
    assert sub.trading_enabled() is True

def test_trading_enabled_default_false():
    assert sub.trading_enabled() is False


# ---------- guards (all with both switches ON) ----------
def test_kill_switch_blocks_everything(monkeypatch):
    go_live(monkeypatch)
    result, client, _ = run(halted=(True, "kill switch file present"))
    assert result["outcome"] == "NOT_SUBMITTED" and "kill switch" in result["reason"]
    assert client.submitted == []

@pytest.mark.parametrize("intent", [
    None,
    {"action": "NONE", "qty": 0, "reason": "x"},
    {"action": "BLOCKED", "qty": 0, "reason": "y"},
    {"action": "BUY", "qty": 0},
    {"action": "HOLD", "qty": 5},
    {"action": "BUY", "qty": True},
    {"action": "BUY", "qty": -3},
])
def test_unactionable_intent_is_not_submitted(monkeypatch, intent):
    go_live(monkeypatch)
    result, client, _ = run(intent=intent)
    assert result["outcome"] == "NOT_SUBMITTED" and client.submitted == []

def test_caps_can_zero_the_order(monkeypatch):
    go_live(monkeypatch)
    result, client, _ = run(current_qty=6.0)        # only ~$570 of position room left
    assert result["outcome"] == "NOT_SUBMITTED" and "caps" in result["reason"]
    assert client.submitted == []

def test_invalid_reference_price_blocks(monkeypatch):
    go_live(monkeypatch)
    result, client, _ = run(ref_price=0.5)
    assert result["outcome"] == "NOT_SUBMITTED" and client.submitted == []

def test_naive_bar_time_blocks(monkeypatch):
    go_live(monkeypatch)
    result, client, _ = run(bar_time=datetime(2026, 11, 17, 14, 35))
    assert result["outcome"] == "NOT_SUBMITTED" and client.submitted == []

@pytest.mark.parametrize("orders", [
    {"status": "OK", "count": 1},
    {"status": "ERROR", "count": None, "orders": None},
    None,
    {"status": "OK", "count": None},
])
def test_open_order_recheck_blocks(monkeypatch, orders):
    go_live(monkeypatch)
    result, client, _ = run(open_orders=orders)
    assert result["outcome"] == "NOT_SUBMITTED" and client.submitted == []

def test_open_orders_function_exception_blocks(monkeypatch):
    go_live(monkeypatch)
    def boom():
        raise RuntimeError("down")
    result, client, _ = run(open_orders=boom)
    assert result["outcome"] == "NOT_SUBMITTED" and client.submitted == []


# ---------- live submission (fake broker) ----------
def test_live_submit_fills(monkeypatch):
    go_live(monkeypatch)
    client = FakeClient(statuses=[("filled", "1")])
    result, client, _ = run(client=client)
    assert result["outcome"] == "SUBMITTED"
    assert result["state"] == "DONE_FILLED" and result["filled_qty"] == 1.0
    assert len(client.submitted) == 1
    req = client.submitted[0]
    assert req.symbol == "SPY" and req.qty == 1
    assert req.side == OrderSide.BUY and req.time_in_force == TimeInForce.DAY
    assert req.limit_price == 738.99 and req.client_order_id == CID

def test_sell_is_not_blocked_by_caps_and_uses_sell_price(monkeypatch):
    go_live(monkeypatch)
    client = FakeClient(statuses=[("filled", "3")], order_qty="3")
    result, client, _ = run(intent={"action": "SELL", "qty": 3, "reason": "t"},
                            client=client, current_qty=3.0)
    assert result["outcome"] == "SUBMITTED" and result["qty"] == 3
    req = client.submitted[0]
    assert req.side == OrderSide.SELL and req.limit_price == 737.51
    assert result["state"] == "DONE_FILLED"

def test_still_active_after_timeout(monkeypatch):
    go_live(monkeypatch)
    result, client, _ = run(client=FakeClient(statuses=[("new", "0")]))
    assert result["outcome"] == "SUBMITTED" and result["state"] == "ACTIVE"
    assert client.lookups == 15                     # 30 s / 2 s
    assert sub.unresolved_submission() is None

def test_partial_fill_is_reported(monkeypatch):
    go_live(monkeypatch)
    client = FakeClient(statuses=[("canceled", "4")], order_qty="10")
    result, _, _ = run(client=client)
    assert result["state"] == "DONE_PARTIAL" and result["filled_qty"] == 4.0

def test_rejected_order_is_not_filled(monkeypatch):
    go_live(monkeypatch)
    result, _, _ = run(client=FakeClient(statuses=[("rejected", "0")]))
    assert result["state"] == "DONE_NOT_FILLED"

def test_submit_error_recovered_by_lookup(monkeypatch):
    go_live(monkeypatch)
    client = FakeClient(submit_error=RuntimeError("duplicate client_order_id"),
                        statuses=[("filled", "1")])
    result, client, _ = run(client=client)
    assert result["outcome"] == "RECOVERED" and result["state"] == "DONE_FILLED"
    assert len(client.submitted) == 1               # never retried
    assert "duplicate" in result["reason"]

def test_submit_error_and_lookup_error_is_unknown_and_latches(monkeypatch):
    go_live(monkeypatch)
    client = FakeClient(submit_error=RuntimeError("boom"),
                        lookup_error=RuntimeError("down"))
    result, client, _ = run(client=client)
    assert result["outcome"] == "SUBMIT_UNKNOWN"
    assert len(client.submitted) == 1               # never retried
    assert sub.unresolved_submission() == CID

def test_latch_blocks_next_order(monkeypatch):
    go_live(monkeypatch)
    run(client=FakeClient(submit_error=RuntimeError("boom"),
                          lookup_error=RuntimeError("down")))
    result, client, _ = run(client=FakeClient(statuses=[("filled", "1")]))
    assert result["outcome"] == "NOT_SUBMITTED" and "unresolved" in result["reason"]
    assert client.submitted == []

def test_clear_latch_allows_orders(monkeypatch):
    go_live(monkeypatch)
    run(client=FakeClient(submit_error=RuntimeError("boom"),
                          lookup_error=RuntimeError("down")))
    sub.clear_unresolved_submission()
    result, client, _ = run(client=FakeClient(statuses=[("filled", "1")]))
    assert result["outcome"] == "SUBMITTED" and len(client.submitted) == 1

def test_polling_lookup_failure_is_unknown_and_latches(monkeypatch):
    go_live(monkeypatch)
    result, _, _ = run(client=FakeClient(lookup_error=RuntimeError("down")))
    assert result["outcome"] == "SUBMITTED" and result["state"] == "UNKNOWN"
    assert sub.unresolved_submission() == CID


# ---------- audit and result shape ----------
def test_audit_events_sequence(monkeypatch):
    go_live(monkeypatch)
    _, _, audit = run(client=FakeClient(statuses=[("filled", "1")]))
    assert [name for name, _ in audit.events] == ["order_submit_attempt", "order_submit"]

def test_result_shape():
    result, _, _ = run()
    assert set(result) == {"outcome", "reason", "symbol", "client_order_id", "order_id",
                           "side", "qty", "limit_price", "state", "filled_qty"}