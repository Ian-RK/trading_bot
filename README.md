# 🤖 Trading Bot: Systematic Price Action Engine

[](https://www.python.org/downloads/)
([https://img.shields.io/badge/License-MIT-yellow.svg](https://www.google.com/search?q=https://img.shields.io/badge/License-MIT-yellow.svg))]([https://opensource.org/licenses/MIT](https://opensource.org/licenses/MIT))
[](https://www.google.com/search?q=%5Bhttps://alpaca.markets/%5D(https://alpaca.markets/))

A robust, regime-specific automated trading system built in Python. This bot utilizes a **4-State Trend Reversal Model** combined with institutional-grade risk filters to identify high-probability entry points while strictly preserving capital during market crashes.

## 📈 Performance Summary (Backtested)

The strategy was rigorously validated across multiple market regimes to ensure it is not "curve-fitted" to a single year.

| Regime | Asset | Total Return | Max Drawdown | Sharpe Ratio |
| --- | --- | --- | --- | --- |
| **Bear Market (2022)** | SPY | +17.32% | -2.11% | 3.92 |
| **High Volatility (2025)** | QQQ | +23.93% | -1.80% | 4.22 |
| **Neutral/Choppy (2018)** | SPY | +1.65% | -9.70% | 0.30 |

---

## ✨ Key Features

* **Regime-Specific Defensive Logic:** Uses an **SMA 200 "Trend Veto"** to automatically sit in cash during structural market crashes, as validated in the 2022 stress test.
* **Realistic Backtesting Engine:** Implements "Next-Day Open" execution to eliminate look-ahead bias and accounts for 0.1% slippage and broker commissions.
* **Regulatory PDT Guard:** Built-in Pattern Day Trader (PDT) protection that monitors the rolling 5-day trade count to prevent account freezing.
* **Reliability Engineering:** Features a 60-second **Stale Data Veto** and an automated **Daily Loss Kill Switch** (-3%) to handle connectivity drops or flash crashes.
* **Headless Observability:** Integrated **Telegram Heartbeat** system for 24/7 monitoring on remote devices like a Raspberry Pi.

---

## 🛠️ Technologies Used

* **Language:** Python 3.12+
* **Data Science:** Pandas, NumPy, Polars (High-speed ingestion).
* **Technical Analysis:** `pandas-ta` (Bollinger Bands, SMA, ATR).
* **Brokerage:** Alpaca Markets API (`alpaca-py`).
* **Communication:** Telegram Bot API (Alerting/Heartbeat).

---

## 🚀 Getting Started

### Prerequisites

* An [Alpaca Markets](https://alpaca.markets/) account (Paper Trading API keys).
* A([https://t.me/botfather](https://t.me/botfather)) token and Chat ID.

### Installation

1. **Clone the Repository:**
```bash
git clone https://github.com/Ian-RK/trading_bot.git
cd trading_bot

```


2. **Set up Virtual Environment:**
```bash
python -m venv trading_bot_env
source trading_bot_env/bin/activate  # Windows:.\trading_bot_env\Scripts\activate
pip install -r requirements.txt

```


3. **Configure Environment Variables:**
Create a `.env` file in the root directory:
```env
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

```



---

## 📖 Usage

### Running a Backtest

To simulate the strategy on historical data stored in the `/data` folder:

```bash
python backtesting_engine.py

```

### Starting the Live Loop (Paper Mode)

To run the bot 24/7 in simulation mode with live data:

```bash
python main.py

```

---

## 🛡️ Risk Management & Safety

The bot operates with multiple safety layers:

1. **Data Sanity:** If incoming market data is >60s old, all trading is vetoed.
2. **PDT Guard:** Refuses new entries if the account has  day trades in a rolling 5-day window.
3. **Circuit Breaker:** Automatically liquidates positions and halts if the portfolio drops >3% in a single day.
4. **Graceful Shutdown:** Handles `SIGINT` (Ctrl+C) by notifying the user and closing logging threads before exiting.

---

## ⚖️ Legal Disclaimer

**This software is for educational purposes only.** Trading financial instruments involves substantial risk of loss. The authors and contributors assume no responsibility for your trading results. **Always start in a Paper Trading (Sandbox) environment.**.

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request for any logic improvements or edge-case protections.

---

## 👨‍💻 Contact Info

**Ian-RK** - [GitHub](https://www.google.com/search?q=https://github.com/Ian-RK)
