"""
Read-only look-ahead check. No API, no orders. Uses the local CSV.
For each row i, compares the signal computed with ALL data (as the backtest
does) against the signal computed using ONLY rows 0..i (all a live bot knows).

Run from the repo root:  python -m scripts.prove_lookahead
"""
import pandas as pd

from strategies.price_action_strategy import engineer_features

PATH = "data/SPY_historical.csv"
START = 200            # the 200-day average needs at least 200 rows

df = pd.read_csv(PATH)
n = len(df)
full = engineer_features(df)["signal_weight"].to_numpy()

full_signals = 0
live_signals = 0
disagree = 0
errors = 0

for i in range(START, n):
    try:
        live = engineer_features(df.iloc[: i + 1])["signal_weight"].iloc[-1]
    except Exception:
        errors += 1
        continue
    if full[i] != 0:
        full_signals += 1
    if live != 0:
        live_signals += 1
    if live != full[i]:
        disagree += 1

checked = n - START - errors
print(f"rows in file: {n}   rows compared: {checked}   errors: {errors}")
print(f"signals computed with ALL data:          {full_signals}")
print(f"signals computed with data up to each day: {live_signals}")
print(f"days where the two disagree:              {disagree} of {checked}")