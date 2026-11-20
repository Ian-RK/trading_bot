import itertools
import re
from datetime import datetime, timedelta, timezone

import pytest

from utils.order_params import build_client_order_id as cid
from utils.order_params import marketable_limit_price as mlp

T = datetime(2026, 11, 17, 14, 35, tzinfo=timezone.utc)


# ---------- client order id ----------
def test_id_format_buy():
    assert cid("SPY", "BUY", T) == "tb1-SPY-buy-20261117T143500Z"

def test_id_format_sell():
    assert cid("SPY", "SELL", T) == "tb1-SPY-sell-20261117T143500Z"

def test_id_is_deterministic():
    assert cid("SPY", "BUY", T) == cid("SPY", "BUY", T)

def test_different_bar_gives_different_id():
    assert cid("SPY", "BUY", T) != cid("SPY", "BUY", T + timedelta(minutes=1))

def test_different_side_gives_different_id():
    assert cid("SPY", "BUY", T) != cid("SPY", "SELL", T)

def test_other_timezone_is_converted_to_utc():
    est = timezone(timedelta(hours=-5))
    local = datetime(2026, 11, 17, 9, 35, tzinfo=est)
    assert cid("SPY", "BUY", local) == cid("SPY", "BUY", T)

def test_id_charset_and_length():
    value = cid("SPY", "BUY", T)
    assert re.fullmatch(r"[A-Za-z0-9-]{1,128}", value)

@pytest.mark.parametrize("symbol", ["", "spy", "SPY1", "S P", None, "TOOLONGSYM"])
def test_invalid_symbol_raises(symbol):
    with pytest.raises(ValueError):
        cid(symbol, "BUY", T)

@pytest.mark.parametrize("side", ["buy", "HOLD", None])
def test_invalid_side_raises(side):
    with pytest.raises(ValueError):
        cid("SPY", side, T)

@pytest.mark.parametrize("bar_time", [datetime(2026, 11, 17, 14, 35), None, "2026-11-17"])
def test_invalid_bar_time_raises(bar_time):
    with pytest.raises(ValueError):
        cid("SPY", "BUY", bar_time)

@pytest.mark.parametrize("prefix", ["", "TB1", "a b", None])
def test_invalid_prefix_raises(prefix):
    with pytest.raises(ValueError):
        cid("SPY", "BUY", T, prefix=prefix)


# ---------- marketable limit price ----------
def test_buy_exact():
    assert mlp("BUY", 100.0) == 100.10

def test_sell_exact():
    assert mlp("SELL", 100.0) == 99.90

def test_buy_real_price():
    assert mlp("BUY", 738.25) == 738.99      # 738.98825 rounded UP

def test_sell_real_price():
    assert mlp("SELL", 738.25) == 737.51     # 737.51175 rounded DOWN

def test_buy_rounds_up_not_nearest():
    assert mlp("BUY", 753.2) == 753.96       # 753.9532 -> up

def test_sell_rounds_down_not_nearest():
    assert mlp("SELL", 753.2) == 752.44      # 752.4468 -> down

def test_buy_higher_price():
    assert mlp("BUY", 1234.56) == 1235.80    # 1235.79456 -> up

def test_sell_higher_price():
    assert mlp("SELL", 1234.56) == 1233.32   # 1233.32544 -> down

def test_returns_float():
    assert type(mlp("BUY", 100.0)) is float

def test_custom_offset():
    assert mlp("BUY", 200.0, offset=0.005) == 201.00
    assert mlp("SELL", 200.0, offset=0.005) == 199.00

def test_invariants_over_many_inputs():
    for ref, offset in itertools.product(
            [1.0, 19.99, 100.0, 738.25, 753.2, 1234.56, 4999.99],
            [0.0005, 0.001, 0.005, 0.01]):
        buy = mlp("BUY", ref, offset)
        sell = mlp("SELL", ref, offset)
        assert buy >= ref and sell <= ref
        assert buy - ref <= ref * offset + 0.0100001
        assert ref - sell <= ref * offset + 0.0100001
        for p in (buy, sell):
            assert abs(p * 100 - round(p * 100)) < 1e-6   # whole cents

@pytest.mark.parametrize("side", ["buy", "HOLD", None])
def test_price_invalid_side_raises(side):
    with pytest.raises(ValueError):
        mlp(side, 100.0)

@pytest.mark.parametrize("ref", [0, -1, 0.5, float("nan"), float("inf"), None, True, "100"])
def test_price_invalid_reference_raises(ref):
    with pytest.raises(ValueError):
        mlp("BUY", ref)

@pytest.mark.parametrize("offset", [0, -0.001, 0.02, float("nan"), None])
def test_price_invalid_offset_raises(offset):
    with pytest.raises(ValueError):
        mlp("BUY", 100.0, offset=offset)