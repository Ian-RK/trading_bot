import numpy as np
import pandas as pd

from strategies.price_action_strategy import engineer_features

N = 300
START = 200   # sma_200 needs at least 200 rows (same as scripts/prove_lookahead)


def _synthetic():
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, N))
    high = close + rng.uniform(0.1, 1.0, N)
    low = close - rng.uniform(0.1, 1.0, N)
    return pd.DataFrame({"high": high, "low": low, "close": close})


def test_signal_and_state_at_row_i_do_not_depend_on_later_rows():
    df = _synthetic()
    full = engineer_features(df)
    full_signal = full["signal_weight"].to_numpy()
    full_state = full["state"].to_numpy()
    for i in range(START, N):
        part = engineer_features(df.iloc[: i + 1])
        assert part["signal_weight"].iloc[-1] == full_signal[i], f"signal differs at row {i}"
        assert part["state"].iloc[-1] == full_state[i], f"state differs at row {i}"


def test_causality_check_is_not_vacuous():
    full = engineer_features(_synthetic())
    assert (full["signal_weight"] != 0).sum() > 0