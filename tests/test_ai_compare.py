from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from utils.ai_compare import (ai_weights, buy_and_hold, combined_weights,
                              compare, decision_cutoff, row_dates)


def make_df(n=30, buys=(5,), sells=(15,)):
    ts = pd.date_range("2025-01-02", periods=n, freq="B", tz="UTC") + pd.Timedelta(hours=5)
    opens = [100 + 0.1 * i for i in range(n)]
    w = [0.0] * n
    for i in buys:
        w[i] = 1.0
    for i in sells:
        w[i] = -1.0
    return pd.DataFrame({
        "timestamp": [str(t) for t in ts],
        "open": opens,
        "close": [o + 0.05 for o in opens],
        "signal_weight": w,
    })


def test_decision_cutoff_winter_and_summer():
    assert decision_cutoff(date(2026, 1, 15)) == datetime(2026, 1, 15, 21, 0, tzinfo=timezone.utc)
    assert decision_cutoff("2026-07-15") == datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)


def test_row_dates_utc_midnight_to_et_day():
    df = pd.DataFrame({"timestamp": ["2025-01-02 05:00:00+00:00",
                                     "2025-07-01 04:00:00+00:00"]})
    assert row_dates(df) == [date(2025, 1, 2), date(2025, 7, 1)]


def test_row_dates_naive_timestamps_unchanged():
    df = pd.DataFrame({"timestamp": ["2025-01-02", "2025-01-03"]})
    assert row_dates(df) == [date(2025, 1, 2), date(2025, 1, 3)]


def test_missing_scores_are_neutral():
    df = make_df()
    dates = row_dates(df)
    price = list(df["signal_weight"])
    assert ai_weights(dates, {}) == [0.0] * len(dates)
    assert combined_weights(price, dates, {}) == price


def test_ai_weights_accept_tuple_dict_and_iso_keys():
    dates = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)]
    scores = {
        date(2025, 1, 2): (0.5, 0.8),
        "2025-01-03": {"score": -0.6, "confidence": 0.9},
        date(2025, 1, 6): (0.0, 0.9),
    }
    assert ai_weights(dates, scores) == [1.0, -1.0, 0.0, 0.0]


def test_combined_vetoes_buys_only():
    d0 = date(2025, 1, 2)
    dates = [d0 + timedelta(days=i) for i in range(4)]
    scores = {
        dates[1]: (-0.8, 0.9),   # bearish and confident: vetoes the buy
        dates[2]: (0.9, 0.9),    # bullish on a sell: sell stays
        dates[3]: (-0.8, 0.1),   # bearish but low confidence: buy stays
    }
    assert combined_weights([0.0, 1.0, -1.0, 0.5], dates, scores) == [0.0, 0.0, -1.0, 0.5]


def test_bad_score_entries_are_neutral():
    dates = [date(2025, 1, 2), date(2025, 1, 3)]
    scores = {dates[0]: "junk", dates[1]: (None, None)}
    assert ai_weights(dates, scores) == [0.0, 0.0]
    assert combined_weights([1.0, 1.0], dates, scores) == [1.0, 1.0]


def test_combined_length_mismatch_raises():
    with pytest.raises(ValueError):
        combined_weights([1.0], [date(2025, 1, 2), date(2025, 1, 3)], {})


def test_buy_and_hold_math():
    df = pd.DataFrame({"open": [100.0, 100.0, 100.0], "close": [100.0, 100.0, 101.0]})
    eq = buy_and_hold(df, 10000.0, 0.01, 0.001)
    # price 100.1, shares int(10000/100.11)=99, cash 10000-9909.9-0.99=89.11
    assert eq.iloc[0] == 10000.0
    assert eq.iloc[1] == pytest.approx(89.11 + 99 * 100.0)
    assert eq.iloc[2] == pytest.approx(89.11 + 99 * 101.0)
    with pytest.raises(ValueError):
        buy_and_hold(df.iloc[:1], 10000.0, 0.01, 0.001)


def test_compare_does_not_mutate_input():
    df = make_df()
    before = df.copy(deep=True)
    compare(df, {row_dates(df)[3]: (0.9, 0.9)})
    pd.testing.assert_frame_equal(df, before)


def test_compare_table_and_notes():
    df = make_df()
    dates = row_dates(df)
    res = compare(df, {dates[2]: (0.9, 0.9), date(2030, 1, 1): (0.9, 0.9)})
    assert list(res["table"].index) == ["price_only", "ai_only", "combined", "buy_and_hold"]
    for col in ("final_equity", "total_return_pct", "max_drawdown_pct",
                "sharpe", "trades", "breaker_fired"):
        assert col in res["table"].columns
    assert res["notes"]["days"] == 30
    assert res["notes"]["scored_days"] == 1      # the 2030 key is outside the data
    assert all(len(e) == 30 for e in res["equity"].values())


def test_neutral_ai_leaves_combined_equal_to_price_only():
    df = make_df()
    scores = {d: (0.0, 0.9) for d in row_dates(df)}
    res = compare(df, scores)
    assert res["equity"]["combined"].tolist() == res["equity"]["price_only"].tolist()
    assert res["table"].loc["ai_only", "trades"] == 0
    assert (res["equity"]["ai_only"] == 10000.0).all()


def test_score_affects_only_next_row_onward():
    df = make_df()
    dates = row_dates(df)
    base = compare(df, {})["equity"]["ai_only"]
    changed = compare(df, {dates[10]: (0.9, 0.9)})["equity"]["ai_only"]
    assert changed.iloc[:11].tolist() == base.iloc[:11].tolist()   # rows 0..10 unchanged
    assert changed.iloc[11] != base.iloc[11]                       # trade at row 11's open


def test_future_scores_do_not_change_past():
    df = make_df()
    dates = row_dates(df)
    shared = {dates[3]: (0.9, 0.9)}
    a = dict(shared)
    b = {**shared, dates[13]: (-0.9, 0.9)}            # differs only from row 13
    assert ai_weights(dates[:13], a) == ai_weights(dates[:13], b)
    ra, rb = compare(df, a)["equity"], compare(df, b)["equity"]
    for name in ("price_only", "ai_only", "combined"):
        assert ra[name].iloc[:14].tolist() == rb[name].iloc[:14].tolist()
    assert ra["ai_only"].iloc[14] != rb["ai_only"].iloc[14]        # not vacuous


def test_breaker_applies_to_engine_runs_not_buy_and_hold():
    df = make_df(n=6, buys=(0,), sells=())
    df.loc[1, "close"] = 94.0                          # about -6% on the first held day
    res = compare(df, {})
    t = res["table"]
    assert bool(t.loc["price_only", "breaker_fired"]) is True
    assert t.loc["price_only", "trades"] == 1
    assert bool(t.loc["buy_and_hold", "breaker_fired"]) is False
    assert t.loc["buy_and_hold", "final_equity"] > t.loc["price_only", "final_equity"]