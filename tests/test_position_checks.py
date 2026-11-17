from types import SimpleNamespace

import pytest

import utils.position_reconciler as pr
import state.position_state as ps
from state.position_state import PositionState


class FakeClient:
    def __init__(self, positions=None, error=None):
        self._positions = positions or []
        self._error = error

    def get_all_positions(self):
        if self._error:
            raise self._error
        return self._positions


def pos(symbol, qty, market_value):
    return SimpleNamespace(symbol=symbol, qty=qty, market_value=market_value)


def use(monkeypatch, client):
    monkeypatch.setattr(pr, "trading_client", client)


# ---------- reconciler ----------
def test_flat_when_no_positions(monkeypatch):
    use(monkeypatch, FakeClient([]))
    assert pr.get_current_position("SPY") == {
        "exists": False, "qty": 0.0, "market_value": 0.0,
        "side": None, "status": "OK"}


def test_flat_when_only_other_symbols(monkeypatch):
    use(monkeypatch, FakeClient([pos("QQQ", "5", "2000")]))
    r = pr.get_current_position("SPY")
    assert r["status"] == "OK" and r["exists"] is False and r["qty"] == 0.0


def test_long_position(monkeypatch):
    use(monkeypatch, FakeClient([pos("SPY", "10", "7500.5")]))
    assert pr.get_current_position("SPY") == {
        "exists": True, "qty": 10.0, "market_value": 7500.5,
        "side": "LONG", "status": "OK"}


def test_fractional_long(monkeypatch):
    use(monkeypatch, FakeClient([pos("SPY", "0.001313718", "0.98986")]))
    r = pr.get_current_position("SPY")
    assert r["status"] == "OK" and r["side"] == "LONG" and r["qty"] == 0.001313718


def test_short_position_is_reported_as_short(monkeypatch):
    use(monkeypatch, FakeClient([pos("SPY", "-5", "-3750")]))
    r = pr.get_current_position("SPY")
    assert r["status"] == "OK" and r["side"] == "SHORT" and r["qty"] == -5.0


def test_listed_position_with_zero_qty_is_not_existing(monkeypatch):
    use(monkeypatch, FakeClient([pos("SPY", "0", "0")]))
    r = pr.get_current_position("SPY")
    assert r["status"] == "OK" and r["exists"] is False and r["side"] is None


def test_api_error_returns_none_values_not_zero(monkeypatch):
    use(monkeypatch, FakeClient(error=RuntimeError("unauthorized")))
    r = pr.get_current_position("SPY")
    assert r == {"exists": None, "qty": None, "market_value": None,
                 "side": None, "status": "ERROR"}


@pytest.mark.parametrize("qty,mv", [
    ("10", None),        # missing market value used to crash the caller
    ("abc", "100"),      # unparseable qty
    ("nan", "100"),      # non-finite qty
    ("10", "inf"),       # non-finite market value
    (None, "100"),       # missing qty
])
def test_bad_position_data_is_error_not_crash(monkeypatch, qty, mv):
    use(monkeypatch, FakeClient([pos("SPY", qty, mv)]))
    r = pr.get_current_position("SPY")
    assert r["status"] == "ERROR" and r["qty"] is None and r["exists"] is None


# ---------- state layer ----------
def fake_result(monkeypatch, result):
    monkeypatch.setattr(ps, "get_current_position", lambda symbol: result)


def ok(qty):
    return {"exists": qty != 0, "qty": qty, "market_value": 1.0,
            "side": None, "status": "OK"}


def test_state_error_is_unknown(monkeypatch):
    fake_result(monkeypatch, {"exists": None, "qty": None, "market_value": None,
                              "side": None, "status": "ERROR"})
    assert ps.determine_position_state("SPY") is PositionState.UNKNOWN


def test_state_zero_is_flat(monkeypatch):
    fake_result(monkeypatch, ok(0.0))
    assert ps.determine_position_state("SPY") is PositionState.FLAT


def test_state_positive_is_long(monkeypatch):
    fake_result(monkeypatch, ok(5.0))
    assert ps.determine_position_state("SPY") is PositionState.LONG


def test_state_tiny_fraction_is_long(monkeypatch):
    fake_result(monkeypatch, ok(0.001))
    assert ps.determine_position_state("SPY") is PositionState.LONG


def test_state_short_is_unknown(monkeypatch):
    fake_result(monkeypatch, ok(-5.0))
    assert ps.determine_position_state("SPY") is PositionState.UNKNOWN


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), True, "5"])
def test_state_non_number_qty_is_unknown(monkeypatch, bad):
    fake_result(monkeypatch, ok(bad))
    assert ps.determine_position_state("SPY") is PositionState.UNKNOWN


def test_state_non_dict_is_unknown(monkeypatch):
    fake_result(monkeypatch, None)
    assert ps.determine_position_state("SPY") is PositionState.UNKNOWN