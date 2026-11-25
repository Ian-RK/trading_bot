# Trading Bot: Price-Action Engine on Alpaca (paper trading)

An experimental Python trading bot built around a price-action strategy and a safety layer designed to fail closed. It is **under development, runs against an Alpaca paper account only, and cannot currently place orders on its own.**

> **Not ready for live trading.** Paper results do not predict real-money results. This is educational software, not financial advice.

## Status

- The safety and execution plumbing is implemented and unit-tested (see below).
- The bot loop runs in paper mode during market hours, evaluates the strategy and logs what it *would* do. It submits nothing.
- A guarded order-submission function exists but is not connected to the bot. It has been tested only with a fake broker and in dry runs, and one forced 1-share paper round trip (buy, duplicate-ID rejection, sell) has been run successfully.
- **The strategy is not validated.** Swing detection is now causal and the backtest uses long-only, next-open semantics. Earlier performance figures came from a look-ahead bug and a sell-from-flat bug and remain **withdrawn**. See the results below: the strategy has about 6 distinct entries, was tuned on the same files, and underperformed buy and hold wherever it traded.
- **Shadow mode:** the bot also polls public news and logs AI sentiment scores each day after the close. This is advisory only and never affects orders.

## What is implemented

**Safety layers**
- **Paper-only guard:** the client is hard-coded to paper; startup refuses unless the account looks like a paper account and any configured base URL is the paper host.
- **Fail-closed checks:** position, open-order and account-health queries return explicit error states, and an error is never treated as "flat".
- **Market-hours logic:** trades only when the market is open, using Eastern-time calendar handling.
- **Stale-data veto:** bars older than 180 seconds (or timestamped in the future) block the cycle; each bar is processed once.
- **Kill switch:** create a file named `KILL_SWITCH` in the repo root to suppress all trading without stopping the bot.
- **Audit log:** every cycle decision is appended to `logs/audit.jsonl` (local, git-ignored).
- **Alerts:** Telegram messages for state changes, errors, blocks and halts, with token redaction.
- **Failure handling:** a failed cycle is retried with backoff; five consecutive failures stop the bot.

**Order logic (not yet wired to the bot)**
- Long-only intent from the strategy weight: positive weights add exposure, negative weights reduce it, `0` means hold; no shorting, whole shares only.
- Hard size caps (paper phase: $1,000 or 1% of equity per order; $5,000 or 5% total position).
- Marketable limit orders, a unique client order ID per bar, order-status classification that accounts for partial fills, and a guarded submit function requiring two independent switches.

## Architecture

```
main.py                     loop: schedule -> bar -> guards -> signal -> dry-run execution -> audit
strategies/                 price_action_strategy.py (features and signal weight)
utils/                      broker, reconcilers, intent, caps, order params/status/submit,
                            schedule, freshness, bar tracker, kill switch, audit log, Telegram
state/                      position state (FLAT / LONG / UNKNOWN)
scripts/                    read-only diagnostics, dry runs, and one guarded paper-order test
tests/                      pytest suites (fakes, no network)
backtesting_engine.py       daily backtest (long-only, next-open execution)
```

Project notes for contributors are kept outside the repository.

## Status and limitations

This is a paper-trading research project. **It does not place orders.**
`main.py` fetches data, computes the daily signal and logs what it would do.
Order submission exists as a tested module and was exercised once by a manual
paper test (1 share bought and sold on the Alpaca paper account), but it is
not connected to the bot loop.

- Strategy: daily bars, decisions from completed bars only, executed at the
  next open in backtests. Swing points are detected causally (a pivot counts
  only once its confirming bars exist).
- Earlier performance figures in this repository's history were withdrawn:
  the old backtest engine could sell from a flat position and the old swing
  detection used future bars. Both were fixed and tested.
- The current strategy has only about 6 distinct entries across the five
  sample files, and its entry rule was chosen on those same files. There is
  no out-of-sample data. Treat the numbers below as a smoke test of the
  pipeline, not as evidence that the strategy works.
- Paper fills prove nothing about real execution quality.

| Data file | Rows (evaluable) | Strategy return (trades) | Buy and hold, same window | Strategy max drawdown | Buy and hold max drawdown |
|---|---|---|---|---|---|
| SPY_NEUTRAL_2018 | 250 (51) | 0.00% (0) | -11.55% | 0.00% | -16.31% |
| SPY_BEAR_2022 | 251 (52) | 0.00% (0) | +3.53% | 0.00% | -7.59% |
| SPY_BULL_2025 | 250 (51) | +0.87% (4) | +4.46% | -3.71% | -5.01% |
| QQQ_TECH_2025 | 243 (44) | -0.24% (1) | +0.77% | -2.16% | -7.73% |
| SPY_historical | 503 (304) | -0.22% (8) | +16.46% | -3.81% | -18.95% |

"Evaluable" counts rows from the first one where the 200-day average exists; the strategy cannot trade before that. Buy and hold is measured over the same window: buy at the next open with the same slippage and commission, no circuit breaker. The strategy was mostly in cash, so its smaller drawdowns reflect low exposure, not demonstrated skill. The two zero-trade files cover about 50 days each and say almost nothing. On the three files where it traded, the strategy returned less than buy and hold and had a worse return-to-drawdown ratio. Full-file figures are in `results/baseline_2026-11-25.txt`.

Over the same window the strategy returned less than buy and hold on all three files where it traded.

## AI layer (advisory, shadow mode)

An LLM (NVIDIA Nemotron via OpenRouter, free tier, 50 requests/day, 40 used
at most) scores one day's public headlines from -1 (bearish) to +1 (bullish)
with a confidence. **The AI never trades.** Any failure, invalid reply, missing
key or exhausted budget gives a neutral score. Scores are cached by model,
prompt version and day.

- `utils/ai_strategy.py` maps scores to long-only weights: AI-only, or a
  price signal with an AI *veto* (a confident bearish score cancels a buy; it
  never creates a buy and never blocks a sell).
- `utils/ai_compare.py` compares price-only, AI-only, combined and
  buy-and-hold on the unchanged backtest engine. Tests check that scores for
  day t+1 or later cannot change any weight or equity up to day t.
- Shadow mode (`utils/shadow_log.py`, hooked into `main.py`) polls Alpaca
  news every 5 minutes, stamps each headline with **our own first-seen time**,
  and scores each weekday after the 16:00 ET cutoff using only headlines seen
  by then. It writes a log and has no order path.

Why no historical AI backtest: Alpaca's news history starts around May 2026,
comes from a single source of small-company items with no SPY tags, and its
timestamps are batch/ingestion times (nothing before 16:00 ET in the days we
probed). A backtest on it would not be point-in-time. Model memory cannot be
ruled out either. So the AI is evaluated only from the day shadow mode began
recording (2026-11-25), and the early comparison shows the pipeline works, not
that the AI adds value. With so few days, any result is statistically weak.

## Getting started

Run these commands from the folder where you want the project created, not from inside an existing clone.

Requirements: Python 3.13, an [Alpaca](https://alpaca.markets/) **paper** account, and optionally a Telegram bot for alerts.

```powershell
git clone https://github.com/Ian-RK/trading_bot.git
cd trading_bot
python -m venv trading_bot_env
.\trading_bot_env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your **paper** keys. Never commit `.env`.

```env
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TRADING_ENABLED=false
```

`TRADING_ENABLED` is the second of two order-submission switches. Leave it `false`.

Historical data lives in `data/` (git-ignored); the downloader in `utils/data_downloader.py` fetches daily bars.

## Usage

```powershell
python -m pytest tests -q                 # unit tests
python main.py                            # paper loop, market hours only, submits nothing
python -m scripts.diagnose_account        # read-only account fields
python -m scripts.dry_run_intent          # print intent decisions from live paper data
python backtesting_engine.py              # daily backtest (results not validated)
```

Halt trading without stopping the bot: `New-Item KILL_SWITCH -ItemType File`. Resume: `Remove-Item KILL_SWITCH`.

## Known limitations

Small, in-sample strategy evidence (see above); the AI layer has no historical evaluation and only a few days of shadow data; live order submission is not connected; no restart recovery, daily loss limit or stop-loss yet; a daily signal repeats every minute, so a once-per-day guard is needed before order wiring; some legacy scripts in `tests/` still call the Alpaca API when imported.

## Roadmap

Collect several weeks of shadow-mode AI scores and compare strategies with `utils/ai_compare.py`; add a once-per-day guard, restart protection and risk controls; wire submission behind both switches; run a multi-week paper forward-test; consider a Raspberry Pi deployment. Live trading would be a separate, gated release.

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss. The authors assume no responsibility for results. Use paper trading only.

## Contact

Ian-RK on [GitHub](https://github.com/Ian-RK)
