"""Compare price-only, AI-only, combined (AI veto) and buy-and-hold.

No network, no files; backtesting_engine is used unchanged on copies.

Score table: {day: (score, confidence)} or {day: {"score":..,"confidence":..}}.
`day` is the ET trading day whose 16:00 ET close the headlines precede. The
engine trades a decision at the NEXT row's open, so a score for day t can
only affect trades from t+1.
"""
import contextlib
import io
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from utils.ai_strategy import ai_weight, combined_weight

ET = ZoneInfo("America/New_York")
DECISION_TIME = time(16, 0)
NEUTRAL = (None, None)


def decision_cutoff(day):
    """16:00 ET on `day` as a tz-aware UTC datetime (headline cutoff)."""
    return datetime.combine(_to_date(day), DECISION_TIME, tzinfo=ET).astimezone(timezone.utc)


def _to_date(d):
    if isinstance(d, datetime):
        raise ValueError("expected a date or 'YYYY-MM-DD', got a datetime")
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return date.fromisoformat(d)
    raise ValueError(f"unsupported day key: {d!r}")


def row_dates(df):
    """ET trading day of each row. tz-aware timestamps are converted to ET."""
    ts = pd.to_datetime(df["timestamp"])
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert(ET)
    return [t.date() for t in ts]


def _pair(v):
    if isinstance(v, dict):
        return v.get("score"), v.get("confidence")
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return v[0], v[1]
    return NEUTRAL


def _table(scores):
    return {_to_date(k): _pair(v) for k, v in (scores or {}).items()}


def ai_weights(dates, scores):
    table = _table(scores)
    return [ai_weight(*table.get(d, NEUTRAL)) for d in dates]


def combined_weights(price_weights, dates, scores):
    if len(price_weights) != len(dates):
        raise ValueError("price_weights and dates must have the same length")
    table = _table(scores)
    return [combined_weight(p, *table.get(d, NEUTRAL))
            for p, d in zip(price_weights, dates)]


def agreement(price_w, ai_w):
    """How the AI-only weight relates to each non-zero price weight."""
    out = {"price_signal_days": 0, "ai_agrees": 0, "ai_disagrees": 0, "ai_neutral": 0}
    for p, a in zip(price_w, ai_w):
        if p == 0:
            continue
        out["price_signal_days"] += 1
        if a == 0:
            out["ai_neutral"] += 1
        elif (p > 0) == (a > 0):
            out["ai_agrees"] += 1
        else:
            out["ai_disagrees"] += 1
    return out


def metrics(equity, initial):
    """Same formulas as backtesting_engine.print_metrics."""
    eq = pd.Series(equity, dtype=float).reset_index(drop=True)
    final = float(eq.iloc[-1])
    total_return = (final / initial - 1) * 100
    max_dd = float((eq / eq.cummax() - 1).min() * 100)
    r = eq.pct_change().dropna()
    sd = r.std()
    sharpe = float(np.sqrt(252) * r.mean() / sd) if len(r) > 1 and sd > 0 else 0.0
    return {"final_equity": final, "total_return_pct": total_return,
            "max_drawdown_pct": max_dd, "sharpe": sharpe}


def buy_and_hold(df, initial, commission, slippage):
    """Outside the engine (no circuit breaker). Same timing and costs as an
    engine buy: decide at row 0's close, buy at row 1's open + slippage."""
    d = df.reset_index(drop=True)
    if len(d) < 2:
        raise ValueError("need at least 2 rows")
    price = float(d["open"].iloc[1]) * (1 + slippage)
    shares = int(initial / (price + commission))
    cash = initial - shares * price - shares * commission
    eq = [float(initial)]
    for i in range(1, len(d)):
        eq.append(cash + shares * float(d["close"].iloc[i]))
    return pd.Series(eq, dtype=float)


def _engine():
    import backtesting_engine
    return backtesting_engine


def run_with_engine(df, weights, engine=None):
    """Run the unchanged engine on a copy, silently.
    Returns (equity Series, trade count, breaker fired)."""
    eng = engine or _engine()
    d = df.copy().reset_index(drop=True)
    d["signal_weight"] = list(weights)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = eng.run_backtest(d)
    lines = buf.getvalue().splitlines()
    trades = sum(1 for ln in lines
                 if ln.startswith("Day ") and (": BUY " in ln or ": SELL " in ln))
    breaker = any(ln.startswith("CRITICAL") for ln in lines)
    return out["total_equity"].reset_index(drop=True), trades, breaker


def compare(df, scores, engine=None):
    """df needs timestamp, open, close, signal_weight (engineer_features output).
    Returns {"table": DataFrame, "equity": {name: Series}, "notes": dict}."""
    eng = engine or _engine()
    d = df.reset_index(drop=True)
    dates = row_dates(d)
    price_w = [float(x) for x in d["signal_weight"]]
    ai_w = ai_weights(dates, scores)
    comb_w = combined_weights(price_w, dates, scores)

    equity, rows = {}, {}
    for name, w in (("price_only", price_w), ("ai_only", ai_w), ("combined", comb_w)):
        eq, trades, breaker = run_with_engine(d, w, engine=eng)
        equity[name] = eq
        rows[name] = {**metrics(eq, eng.INITIAL_CAPITAL),
                      "trades": trades, "breaker_fired": bool(breaker)}
    bh = buy_and_hold(d, eng.INITIAL_CAPITAL, eng.COMMISSION_PER_SHARE, eng.SLIPPAGE_PCT)
    equity["buy_and_hold"] = bh
    rows["buy_and_hold"] = {**metrics(bh, eng.INITIAL_CAPITAL),
                            "trades": 1, "breaker_fired": False}

    table = _table(scores)
    notes = {
        "days": len(d),
        "scored_days": sum(1 for x in dates if table.get(x, NEUTRAL) != NEUTRAL),
        "vetoed_buys": sum(1 for p, c in zip(price_w, comb_w) if p > 0 and c == 0),
        **agreement(price_w, ai_w),
    }
    return {"table": pd.DataFrame(rows).T, "equity": equity, "notes": notes}