import pandas as pd

from backtesting_engine import run_backtest, INITIAL_CAPITAL


def _frame(signals, opens, closes):
    return pd.DataFrame({"signal_weight": signals, "open": opens, "close": closes})


def test_sell_signal_from_flat_does_nothing():
    df = _frame([-0.5, 0, 0], [100.0] * 3, [100.0] * 3)
    out = run_backtest(df)
    assert (out["total_equity"] == INITIAL_CAPITAL).all()


def test_buy_from_flat_invests_and_pays_costs():
    df = _frame([1.0, 0, 0], [100.0, 100.0, 100.0], [100.0, 100.0, 100.0])
    out = run_backtest(df)
    final = out["total_equity"].iloc[-1]
    assert INITIAL_CAPITAL * 0.99 < final < INITIAL_CAPITAL


def test_smaller_buy_signal_never_reduces_a_larger_position():
    # Buy ~100%, then a 0.5 signal arrives. Price then doubles at the last close.
    df = _frame([1.0, 0.5, 0, 0],
                [100.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 200.0])
    out = run_backtest(df)
    assert out["total_equity"].iloc[-1] > 19000     # still fully invested