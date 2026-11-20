# Trading Bot: Price-Action Engine on Alpaca (paper trading)

An experimental Python trading bot built around a price-action strategy and a safety layer designed to fail closed. It is **under development, runs against an Alpaca paper account only, and cannot currently place orders on its own.**

> **Not ready for live trading.** Paper results do not predict real-money results. This is educational software, not financial advice.

## Status

- The safety and execution plumbing is implemented and unit-tested (see below).
- The bot loop runs in paper mode during market hours, evaluates the strategy and logs what it *would* do. It submits nothing.
- A guarded order-submission function exists but is not connected to the bot. It has been tested only with a fake broker and in dry runs, and one forced 1-share paper round trip (buy, duplicate-ID rejection, sell) has been run successfully.
- **The strategy is not validated.** The swing-detection step uses future bars, so earlier backtest figures were contaminated by look-ahead bias and have been **withdrawn**. The live path also cannot produce a signal on the newest bar until this is fixed. No performance claim is made.

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
backtesting_engine.py       daily backtest (needs updating to current order semantics)
```

Details for contributors and AI assistants: `PROJECT_CONTEXT.md` (architecture and interfaces), `CURRENT_STATE.md` (status, tests, known issues, next task), `DECISIONS.md` (rationale).

## Getting started

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

Strategy look-ahead and a daily-versus-minute data mismatch (see `CURRENT_STATE.md`); live order submission not connected; no restart recovery, daily loss limit or stop-loss yet; some legacy scripts in `tests/` still call the Alpaca API when imported.

## Roadmap

Wire submission behind both switches, make the strategy causal and re-validate it, add risk controls and restart protection, run a multi-week paper forward-test, then consider AI sentiment in shadow mode and a Raspberry Pi deployment. Live trading would be a separate, gated release.

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss. The authors assume no responsibility for results. Use paper trading only.

## Contact

Ian-RK on [GitHub](https://github.com/Ian-RK)
