from utils.ai_strategy import ai_weight, combined_weight


def test_ai_buy():
    assert ai_weight(0.5, 0.8) == 1.0


def test_ai_sell():
    assert ai_weight(-0.6, 0.9) == -1.0


def test_ai_neutral_band():
    assert ai_weight(0.1, 0.9) == 0.0
    assert ai_weight(-0.1, 0.9) == 0.0
    assert ai_weight(0.0, 0.7) == 0.0


def test_ai_low_confidence_is_neutral():
    assert ai_weight(0.9, 0.4) == 0.0
    assert ai_weight(-0.9, 0.0) == 0.0


def test_ai_invalid_inputs_are_neutral():
    assert ai_weight(2.0, 0.5) == 0.0
    assert ai_weight(0.5, 1.5) == 0.0
    assert ai_weight("0.5", 0.5) == 0.0
    assert ai_weight(True, 0.5) == 0.0
    assert ai_weight(float("nan"), 0.5) == 0.0


def test_ai_threshold_boundaries():
    assert ai_weight(0.2, 0.5) == 1.0
    assert ai_weight(-0.2, 0.5) == -1.0


def test_combined_keeps_buy_when_ai_neutral_or_bullish():
    assert combined_weight(1.0, 0.0, 0.7) == 1.0
    assert combined_weight(0.5, 0.8, 0.9) == 0.5


def test_combined_vetoes_buy_when_ai_bearish_confident():
    assert combined_weight(1.0, -0.5, 0.8) == 0.0
    assert combined_weight(0.5, -0.2, 0.5) == 0.0


def test_combined_low_conf_does_not_veto():
    assert combined_weight(1.0, -0.9, 0.4) == 1.0


def test_combined_never_creates_buy():
    assert combined_weight(0.0, 0.9, 0.9) == 0.0


def test_combined_never_blocks_sell():
    assert combined_weight(-1.0, 0.9, 0.9) == -1.0
    assert combined_weight(-0.5, 0.9, 0.9) == -0.5


def test_combined_passes_through_size_and_invalid_ai():
    assert combined_weight(0.5, 0.1, 0.9) == 0.5
    assert combined_weight(0.5, "bad", 0.9) == 0.5
    assert combined_weight(9.0, 0.0, 0.9) == 0.0