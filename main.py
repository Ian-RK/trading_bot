"""
Filename: main.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: This script is a loop that now performs the 
Data Sanity Check first, then the PDT Guard, generates the 
signal, and finally triggers the trade.
"""

import time
import signal
import sys
import pandas as pd
from datetime import datetime, timezone, timedelta

# Import your custom modules
from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.requests import GetCalendarRequest
from utils.tele_monitor import send_telegram_message
from utils.risk_management import is_pdt_safe, trading_client
from utils.data_downloader import client as data_client
from utils.execution_agent import execute_weighted_trade
from strategies.price_action_strategy import engineer_features

# SETTINGS
SYMBOL = "SPY"
# For now, because I am using the Alpaca Free (Basic) Data Plan,
# there is a 15 min delay for each bar
# STALE_THRESHOLD_SECONDS = 60 # Supposed Maximum allowed delay
STALE_THRESHOLD_SECONDS = 960 # Maximum allowed delay
BUFFER_MINUTES = 3             # Safety lead/lag for market hours
EXIT_WINDOW_MINUTES = 20       # Time after close to process final bars (15 delay + 5 margin)

# --- MANUAL SHUTDOWN HANDLER ---
def manual_shutdown(sig, frame):
    print("\nSHUTDOWN SIGNAL RECEIVED.")
    send_telegram_message("🛑 <b>Bot shutting down manually...</b>")

    # Add logic here to close positions if desired
    try:
        # CRITICAL SAFETY: Cancel unfilled orders before going offline
        trading_client.cancel_orders()
        print("Safety: All open orders cancelled.")
    except Exception as e:
        print(f"Cleanup Warning: {e}")
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
Checks Alpaca Calendar to decide if the bot should be active or deep sleep.
Returns True if the bot should run the trading cycle, False if it just woke up.
"""
def manage_market_schedule():
    clock = trading_client.get_clock()
    now = datetime.now(timezone.utc)
    
    # 1. MARKET IS CURRENTLY OPEN
    if clock.is_open:
        # We perform no extra sleep here; the main loop will run at 1-min intervals
        return True
    
    # 2. Check today's status via Calendar API
    today = now.date()
    calendar = trading_client.get_calendar(GetCalendarRequest(start=today, end=today))

    # 3. Handle Holidays/Weekends (Calendar is empty for non-trading days)
    if not calendar:
        print(f"📅 {today}: Market Holiday or Weekend.")
    else:
        # It is a trading day, but market is currently closed.
        # Check buffers (Pre-open and Post-close)
        market_day = calendar
        
        # Buffer A: 3-min warm-up before opening
        # Convert calendar string times to UTC datetimes for comparison
        market_open_utc = market_day.open.replace(tzinfo=timezone.utc)
        market_close_utc = market_day.close.replace(tzinfo=timezone.utc)
        
        if now >= (market_open_utc - timedelta(minutes=BUFFER_MINUTES)) and now < market_open_utc:
            print("Warm-up: Market opening in < 3 mins.")
            return True
            
        # Buffer B: 20-min processing window after close (Handles 15min data lag)
        if now >= market_close_utc and now < (market_close_utc + timedelta(minutes=EXIT_WINDOW_MINUTES)):
            print("Cool-down: Processing final delayed bars.")
            return True

    # 4. MARKET IS CLOSED -> CHECK BUFFERS
    # Calculate sleep until (Next Open - 3 Minutes)
    open_buffer_start = clock.next_open - timedelta(minutes=BUFFER_MINUTES)
    sleep_seconds = (open_buffer_start - now).total_seconds()

    # 5. DEEP SLEEP (Market is truly dark/Holiday)    
    if sleep_seconds > 0:
        next_open_str = clock.next_open.strftime('%A, %b %d at %H:%M UTC')
        msg = f"💤 <b>Market Closed</b>\nNext Session: {next_open_str}\n<i>Bot entering deep sleep...</i>"
        print(msg)
        send_telegram_message(msg)
        
        time.sleep(sleep_seconds)
        send_telegram_message("🌅 <b>Waking Up...</b>\nSafety buffer active (3 mins).")
        return False
        
    return True

"""
@brief This function checks if the live bar is safe to be traded
"""
def run_trading_cycle():
    print(f"\n--- Cycle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Fetch live data
    request_params = StockLatestBarRequest(symbol_or_symbols=SYMBOL)
    latest_bar_dict = data_client.get_stock_latest_bar(request_params)
    latest_bar = latest_bar_dict[SYMBOL]
    
    current_price = latest_bar.close
    bar_time = latest_bar.timestamp
    
    # 2. Data Integrity & Risk Guards
    if not data_is_fresh(bar_time) or not is_pdt_safe():
        return
        
    # 3. DATA FUSION: Injecting the live bar into historical data
    # Load historical data
    hist_df = pd.read_csv(f"data/{SYMBOL}_historical.csv")
    
    # Convert latest_bar object to a single-row DataFrame
    live_row = pd.DataFrame([{
        'timestamp': latest_bar.timestamp,
        'open': latest_bar.open,
        'high': latest_bar.high,
        'low': latest_bar.low,
        'close': latest_bar.close,
        'volume': latest_bar.volume
    }])

    # Combine history + current live bar
    # Append the live row to the history so indicators (SMA 200) see it
    full_df = pd.concat([hist_df, live_row], ignore_index=True)

    # 4. Generate Signal from the 'Fused' data
    # We pass the full_df directly to a slightly modified version of our strategy
    # Note: Ensure price_action_strategy.py can accept a DataFrame instead of just a path
    processed_df = engineer_features(full_df) 
    latest_signal = processed_df['signal_weight'].iloc[-1]

    # 6. Execution Agent
    if latest_signal!= 0:
        order = execute_weighted_trade(SYMBOL, latest_signal, current_price)
        if order:
            side_str = order.side.value.upper()
            msg = f"✅ <b>{side_str} ORDER PLACED</b>\nQty: {order.qty} {SYMBOL} @ ${current_price:.2f}"
            print(msg)
            send_telegram_message(msg)
    else:
        print("LOGIC: No signal detected. Holding cash/shares.")

if __name__ == "__main__":
    send_telegram_message("🤖 <b>Bot Active in Paper Mode</b>")
    try:
        while True:
            # Step 1: Manage Market State (Notifications & Sleeping)
            if manage_market_schedule():
                # Step 2: Run Strategy Logic
                run_trading_cycle()
                
                # Step 3: Standard Heartbeat Interval
                time.sleep(60)

    except Exception as e:
        send_telegram_message(f"🚨 <b>CRITICAL ERROR:</b> Bot crashed! \n{e}")