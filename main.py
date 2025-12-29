"""
Filename: main.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: This script is a loop that now performs the 
Data Sanity Check first, then the PDT Guard, generates the 
signal, and finally triggers the trade.
"""

import os
import time
import signal
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Import your custom modules
from alpaca.data.requests import StockLatestBarRequest
from utils.tele_monitor import send_telegram_message
from utils.risk_management import is_pdt_safe
from utils.risk_management import trading_client
from utils.data_downloader import client as data_client
from utils.execution_agent import execute_weighted_trade
from strategies.price_action_strategy import engineer_features

# SETTINGS
SYMBOL = "SPY"
# For now, because I am using the Alpaca Free (Basic) Data Plan,
# there is a 15 min delay for each bar
# STALE_THRESHOLD_SECONDS = 60 # Supposed Maximum allowed delay
STALE_THRESHOLD_SECONDS = 960 # Maximum allowed delay

# --- MANUAL SHUTDOWN HANDLER ---
def manual_shutdown(sig, frame):
    print("\n⚠️ SHUTDOWN SIGNAL RECEIVED.")
    send_telegram_message("🛑 *Bot shutting down manually...*")
    # Add logic here to close positions if desired
    sys.exit(0)

# Register the handler for Ctrl+C (SIGINT)
signal.signal(signal.SIGINT, manual_shutdown)

"""
@brief Checks if the data timestamp is within the allowed buffer.
@param latest_bar_time last time that the bar was read
@return T/F based on how old the stock bar is 
"""
def data_is_fresh(latest_bar_time):
    now_utc = datetime.now(timezone.utc)
    delay = (now_utc - latest_bar_time).total_seconds()
    
    if delay > STALE_THRESHOLD_SECONDS:
        error_msg = f"⚠️ STALE DATA DETECTED: {SYMBOL} data is {delay:.1f}s old. Vetoing trade."
        print(error_msg)
        send_telegram_message(error_msg) 
        return False
    return True

"""
@brief This function checks if the live bar is safe to be traded
"""
def run_trading_cycle():
    # 1. Check if Market is Open
    # We use the trading_client initialized at risk_management.py
    clock = trading_client.get_clock()
    
    if not clock.is_open:
        print(f"💤 Market is CLOSED. Next open: {clock.next_open}")
        return
    
    print(f"\n--- Cycle Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 2. Fetch live data
    request_params = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
    latest_bar_dict = data_client.get_stock_latest_bar(request_params)
    latest_bar = latest_bar_dict[SYMBOL]
    
    current_price = latest_bar.close
    bar_time = latest_bar.timestamp
    
    # 3. Data Integrity & Risk Guards
    if not data_is_fresh(bar_time):
        return
    if not is_pdt_safe():
        return
        
    print("LOGIC: Data is fresh. Risk checks passed. Ready for signal generation.")

    # 4. Generate Signal from Logic (SMA 200 + Bollinger Bands)
    # We pass the CSV path for the "Warm-up" period calculations
    processed_df = engineer_features(f"data/{SYMBOL}_historical.csv")
    latest_signal = processed_df['signal_weight'].iloc[-1]

    # 5. Execution Agent
    if latest_signal!= 0:
        order = execute_weighted_trade(SYMBOL, latest_signal, current_price)
        if order:
            msg = f"✅ ORDER PLACED: {order.side} {order.qty} {SYMBOL} @ approx ${current_price}"
            print(msg)
            send_telegram_message(msg)
    else:
        print("LOGIC: No signal detected. Holding cash/shares.")

if __name__ == "__main__":
    send_telegram_message("🤖 *Bot Active in Paper Mode*")
    try:
        while True:
            run_trading_cycle()
            time.sleep(60) # Wait 1 minute for the next bar
    except Exception as e:
        send_telegram_message(f"🚨 *CRITICAL ERROR:* Bot crashed! \n{e}")