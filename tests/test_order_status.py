from types import SimpleNamespace

import pytest

from utils.order_status import (ACTIVE_STATUSES, REJECT_LIKE, TERMINAL_BY_FILL,
                                blocks_new_orders, classify_order as c)

TERMINAL = ["canceled", "expired", "done_for_day", "calculated"]


def state(*args):
    return c(*args)["state"]


# ---------- active ----------
@pytest.mark.parametrize("status", [
    "new", "accepted", "pending_new", "accepted_for_bidding", "pending_review",
    "held", "pending_cancel", "pending_replace", "stopped"])
def test_active_statuses(status):
    assert state(status, "10", "0") == "ACTIVE"

def test_partially_filled_is_active_and_reports_fill():
    r = c("partially_filled", "10", "4")
    assert r["state"] == "ACTIVE" and r["filled_qty"] == 4.0


# ---------- filled ----------
def test_filled_in_full():
    assert state("filled", "10", "10") == "DONE_FILLED"

@pytest.mark.parametrize("filled", ["4", "0"])
def test_filled_status_must_match_qty(filled):
    assert state("filled", "10", filled) == "UNKNOWN"


# ---------- terminal statuses are judged by the fill ----------
@pytest.mark.parametrize("status", TERMINAL)
def test_terminal_without_fills(status):
    assert state(status, "10", "0") == "DONE_NOT_FILLED"

@pytest.mark.parametrize("status", TERMINAL)
def test_terminal_with_partial_fill_is_flagged(status):
    r = c(status, "133", "40")            # the "canceled but partly filled" case
    assert r["state"] == "DONE_PARTIAL" and r["filled_qty"] == 40.0

@pytest.mark.parametrize("status", TERMINAL)
def test_terminal_with_full_fill(status):
    assert state(status, "10", "10") == "DONE_FILLED"

@pytest.mark.parametrize("status", ["rejected", "suspended"])
def test_reject_like_without_fills(status):
    assert state(status, "10", "0") == "DONE_NOT_FILLED"

@pytest.mark.parametrize("status", ["rejected", "suspended"])
def test_reject_like_with_fills_is_unknown(status):
    assert state(status, "10", "1") == "UNKNOWN"


# ---------- unsupported / malformed ----------
@pytest.mark.parametrize("status", ["replaced", "weird", None, 123, ""])
def test_unsupported_or_missing_status_is_unknown(status):
    assert state(status, "10", "0") == "UNKNOWN"

def test_enum_like_status_object():
    assert state(SimpleNamespace(value="filled"), "10", "10") == "DONE_FILLED"

def test_status_is_case_insensitive():
    assert state("FILLED", "10", "10") == "DONE_FILLED"

def test_numeric_inputs_are_accepted():
    assert state("filled", 10, 10.0) == "DONE_FILLED"

@pytest.mark.parametrize("qty", [None, "abc", "0", "-5", "nan", "inf", True])
def test_invalid_qty_is_unknown(qty):
    assert state("new", qty, "0") == "UNKNOWN"

@pytest.mark.parametrize("filled", [None, "abc", "-1", "nan", "11", True])
def test_invalid_or_excess_filled_qty_is_unknown(filled):
    assert state("new", "10", filled) == "UNKNOWN"

def test_fractional_quantities():
    assert state("filled", "0.001313718", "0.001313718") == "DONE_FILLED"


# ---------- result shape ----------
def test_result_shape():
    r = c("filled", "1", "1")
    assert set(r) == {"state", "filled_qty", "reason"}
    assert isinstance(r["filled_qty"], float)

def test_unknown_has_no_filled_qty():
    assert c("new", "abc", "0")["filled_qty"] is None


# ---------- blocking ----------
@pytest.mark.parametrize("st, expected", [
    ("ACTIVE", True), ("UNKNOWN", True), ("garbage", True),
    ("DONE_FILLED", False), ("DONE_PARTIAL", False), ("DONE_NOT_FILLED", False)])
def test_blocks_new_orders(st, expected):
    assert blocks_new_orders(st) is expected


# ---------- the installed SDK's statuses are all handled on purpose ----------
def test_every_installed_sdk_status_is_handled_explicitly():
    from alpaca.trading.enums import OrderStatus
    handled = (set(ACTIVE_STATUSES) | set(TERMINAL_BY_FILL) | set(REJECT_LIKE)
               | {"filled", "replaced"})
    missing = {s.value for s in OrderStatus} - handled
    assert not missing, f"unhandled statuses: {sorted(missing)}"