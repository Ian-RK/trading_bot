import itertools
import math

import pytest

from utils.risk_limits import RiskLimits, apply_caps

# Defaults used below: price 100, equity 100,000
#   -> order cap $1,000 (10 shares), position cap $5,000 (50 shares)


def buy(qty, price=100.0, equity=100_000.0, current=0.0, **kw):
    return apply_caps("BUY", qty, price, equity, current, **kw)


def sell(qty, price=100.0, equity=100_000.0, current=0.0, **kw):
    return apply_caps("SELL", qty, price, equity, current, **kw)


# ---------- buys ----------
def test_buy_within_caps_is_unchanged():
    r = buy(5)
    assert r["qty"] == 5 and r["capped"] is False

def test_buy_capped_by_order_cap():
    r = buy(50)
    assert r["qty"] == 10 and r["capped"] is True

def test_buy_capped_by_position_room():
    r = buy(10, current=45.0)          # room = 5000 - 4500 = 500 -> 5 shares
    assert r["qty"] == 5 and r["capped"] is True

def test_buy_at_position_cap_gives_zero():
    r = buy(5, current=50.0)
    assert r["qty"] == 0 and "position cap" in r["reason"]

def test_buy_over_position_cap_gives_zero():
    assert buy(5, current=60.0)["qty"] == 0

def test_percent_cap_binds_on_small_account():
    # equity 10,000: order cap = min(1000, 100) = 100 -> 2 shares at $50
    assert buy(10, price=50.0, equity=10_000.0)["qty"] == 2

def test_dollar_cap_binds_on_large_account():
    # equity 1,000,000: order cap = min(1000, 10000) = 1000 -> 10 shares
    assert buy(100, equity=1_000_000.0)["qty"] == 10

def test_one_share_too_expensive_for_order_cap():
    r = buy(1, price=1500.0)
    assert r["qty"] == 0 and "order cap" in r["reason"]

def test_buy_with_fractional_dust_position():
    assert buy(5, current=0.001313718)["qty"] == 5

def test_custom_limits_are_used():
    big = RiskLimits(max_order_usd=2000.0, max_order_pct=0.05,
                     max_position_usd=10_000.0, max_position_pct=0.10)
    assert buy(50, limits=big)["qty"] == 20

def test_zero_qty_is_nothing_to_do():
    r = buy(0)
    assert r["qty"] == 0 and r["capped"] is False

def test_result_qty_is_int():
    assert type(buy(5)["qty"]) is int


# ---------- sells ----------
def test_sell_passes_through_even_when_over_position_cap():
    r = sell(60, current=60.0)
    assert r["qty"] == 60 and r["capped"] is False

def test_sell_limited_to_whole_shares_held():
    r = sell(10, current=7.9)
    assert r["qty"] == 7 and r["capped"] is True

def test_sell_with_nothing_held_is_zero():
    assert sell(5, current=0.0)["qty"] == 0


# ---------- invalid input fails closed ----------
@pytest.mark.parametrize("action", ["HOLD", None, "buy"])
def test_invalid_action(action):
    r = apply_caps(action, 5, 100.0, 100_000.0, 0.0)
    assert r["qty"] == 0 and r["reason"].startswith("invalid input")

@pytest.mark.parametrize("qty", [-1, 1.5, True, None, "5"])
def test_invalid_qty(qty):
    r = buy(qty)
    assert r["qty"] == 0 and r["reason"].startswith("invalid input")

@pytest.mark.parametrize("price", [0, -1.0, float("nan"), None, float("inf")])
def test_invalid_price(price):
    r = buy(5, price=price)
    assert r["qty"] == 0 and r["reason"].startswith("invalid input")

@pytest.mark.parametrize("equity", [0, -5.0, float("nan"), None])
def test_invalid_equity(equity):
    r = buy(5, equity=equity)
    assert r["qty"] == 0 and r["reason"].startswith("invalid input")

@pytest.mark.parametrize("current", [-1.0, float("nan"), None, True])
def test_invalid_current_qty(current):
    r = buy(5, current=current)
    assert r["qty"] == 0 and r["reason"].startswith("invalid input")

@pytest.mark.parametrize("limits", [
    RiskLimits(max_order_usd=0),
    RiskLimits(max_position_pct=float("nan")),
    None,
    {"max_order_usd": 1000},
])
def test_invalid_limits(limits):
    r = buy(5, limits=limits)
    assert r["qty"] == 0 and r["reason"].startswith("invalid input")


# ---------- invariants over many combinations ----------
def test_buys_never_break_the_caps():
    limits = RiskLimits()
    for price, equity, current, qty in itertools.product(
            [20.0, 99.99, 738.25, 1500.0],
            [5_000.0, 100_000.0, 2_000_000.0],
            [0.0, 0.5, 3.0, 45.0, 200.0],
            [1, 7, 500]):
        r = apply_caps("BUY", qty, price, equity, current)
        order_cap = min(limits.max_order_usd, limits.max_order_pct * equity)
        position_cap = min(limits.max_position_usd, limits.max_position_pct * equity)
        assert 0 <= r["qty"] <= qty
        assert r["qty"] * price <= order_cap + 1e-6
        if r["qty"] > 0:
            assert (current + r["qty"]) * price <= position_cap + 1e-6