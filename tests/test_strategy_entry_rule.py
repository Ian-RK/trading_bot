import os

import pytest

from strategies.price_action_strategy import engineer_features

PATH = "data/SPY_historical.csv"


@pytest.mark.skipif(not os.path.exists(PATH), reason="local data file not present")
def test_every_buy_satisfies_the_entry_rule():
    df = engineer_features(PATH)
    buys = df[df["signal_weight"] > 0]
    assert len(buys) > 0
    dip_recent = (df["close"] <= df["bb_lower"]).astype(int).rolling(10, min_periods=1).max() > 0
    assert (df.loc[buys.index, "close"] > df.loc[buys.index, "sma_200"]).all()
    assert dip_recent.loc[buys.index].all()
    assert df.loc[buys.index, "state"].isin(["LH", "LL"]).all()