"""Map advisory AI scores to long-only backtest weights (no network, no files).

ai_weight: standalone AI signal.
combined_weight: price signal with an AI veto only.
"""
import math

BUY_THRESHOLD = 0.2
SELL_THRESHOLD = -0.2
MIN_CONFIDENCE = 0.5


def _num(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    f = float(x)
    return f if math.isfinite(f) else None


def ai_weight(score, confidence, buy_threshold=BUY_THRESHOLD,
              sell_threshold=SELL_THRESHOLD, min_confidence=MIN_CONFIDENCE):
    """1.0 = buy, -1.0 = sell to flat, 0.0 = no instruction. Invalid -> 0.0."""
    s, c = _num(score), _num(confidence)
    if s is None or c is None:
        return 0.0
    if not (-1.0 <= s <= 1.0 and 0.0 <= c <= 1.0):
        return 0.0
    if c < min_confidence:
        return 0.0
    if s >= buy_threshold:
        return 1.0
    if s <= sell_threshold:
        return -1.0
    return 0.0


def combined_weight(price_weight, ai_score, ai_confidence,
                    sell_threshold=SELL_THRESHOLD,
                    min_confidence=MIN_CONFIDENCE):
    """AI veto only: a confident bearish AI turns a price buy into 0.0.

    Sells and zeros pass through unchanged. Invalid AI input keeps the price
    weight (treated as neutral). Size is never changed.
    """
    p = _num(price_weight)
    if p is None or not (-1.0 <= p <= 1.0):
        return 0.0
    if p <= 0:
        return p
    s, c = _num(ai_score), _num(ai_confidence)
    if s is None or c is None or c < min_confidence:
        return p
    if s <= sell_threshold:
        return 0.0
    return p