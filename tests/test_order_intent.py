import math
import pytest
from utils.order_intent import compute_order_intent

PRICE = 100.0
EQUITY = 10_000.0


def run(weight, qty=0.0, price=PRICE, equity=EQUITY, position="default", orders="default"):
    if position == "default":
        position = {"status": "OK", "qty": qty}
    if orders == "default":
        orders = {"status": "OK", "count": 0}
    return compute_order_intent(weight, price, equity, position, orders)


def check(result, action, qty=0):
    assert result["action"] == action, result
    assert result["qty"] == qty, result


# --- buys ---
def test_full_buy_from_flat():
    check(run(1.0), "BUY", 100)

def test_half_buy_from_flat():
    check(run(0.5), "BUY", 50)

def test_buy_tops_up_partial_position():
    check(run(1.0, qty=40), "BUY", 60)

def test_buy_at_target_does_nothing():
    check(run(1.0, qty=100), "NONE")

def test_buy_signal_never_trims_a_larger_position():
    check(run(0.5, qty=100), "NONE")

def test_buy_gap_under_one_share():
    check(run(1.0, price=20_000.0), "NONE")

# --- sells ---
def test_sell_signal_never_opens_from_flat():
    check(run(-0.5), "NONE")
    check(run(-1.0), "NONE")

def test_half_reduce():
    check(run(-0.5, qty=100), "SELL", 50)

def test_full_exit():
    check(run(-1.0, qty=100), "SELL", 100)

def test_reduce_when_already_below_target_does_nothing():
    check(run(-0.5, qty=30), "NONE")

def test_exit_with_fractional_dust_sells_whole_shares_only():
    check(run(-1.0, qty=100.7), "SELL", 100)

def test_exit_with_less_than_one_share_does_nothing():
    check(run(-1.0, qty=0.5), "NONE")

@pytest.mark.parametrize("qty", [0.4, 1, 3, 7.9, 100, 250.5])
def test_never_sells_more_than_held(qty):
    r = run(-1.0, qty=qty)
    assert r["qty"] <= math.floor(qty), r

# --- no instruction ---
def test_zero_weight_is_no_instruction():
    check(run(0.0, qty=100), "NONE")

def test_zero_weight_is_none_even_if_broker_data_is_bad():
    check(run(0.0, position={"status": "ERROR", "qty": 0.0}), "NONE")

# --- invalid weights ---
@pytest.mark.parametrize("w", [1.5, -1.5, float("nan"), float("inf"), None, "1.0", True])
def test_invalid_weight_is_blocked(w):
    check(run(w), "BLOCKED")

# --- open orders ---
@pytest.mark.parametrize("w", [1.0, 0.5, -0.5, -1.0])
def test_open_order_blocks_everything(w):
    check(run(w, qty=100, orders={"status": "OK", "count": 1}), "BLOCKED")

def test_failed_open_orders_query_blocks():
    check(run(1.0, orders={"status": "ERROR", "count": None, "orders": None}), "BLOCKED")

def test_missing_open_orders_blocks():
    check(run(1.0, orders=None), "BLOCKED")

def test_ok_status_with_bad_count_blocks():
    check(run(1.0, orders={"status": "OK", "count": None}), "BLOCKED")

# --- position problems ---
def test_failed_position_query_blocks():
    check(run(1.0, position={"status": "ERROR", "qty": 0.0}), "BLOCKED")

def test_missing_position_blocks():
    check(run(1.0, position=None), "BLOCKED")

def test_short_position_blocks():
    check(run(-1.0, position={"status": "OK", "qty": -5.0}), "BLOCKED")

def test_ok_status_with_none_qty_blocks():
    check(run(1.0, position={"status": "OK", "qty": None}), "BLOCKED")

# --- price / equity ---
@pytest.mark.parametrize("p", [0, -1.0, float("nan"), None])
def test_bad_price_blocks(p):
    check(run(1.0, price=p), "BLOCKED")

@pytest.mark.parametrize("e", [0, -5.0, float("nan"), None])
def test_bad_equity_blocks(e):
    check(run(1.0, equity=e), "BLOCKED")