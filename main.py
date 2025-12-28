import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Import your custom modules
from utils.tele_monitor import send_telegram_message
from utils.risk_management import is_pdt_safe
from utils.data_downloader import client as data_client
from strategies.price_action_strategy import engineer_features

# SETTINGS
SYMBOL = "SPY"
STALE_THRESHOLD_SECONDS = 60 # Maximum allowed delay

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
        # Uncomment below to get phone alerts for connection drops
        # send_telegram_message(error_msg) 
        return False
    return True

"""
@brief This function checks if the live bar is safe to be traded
"""
def run_trading_cycle():
    print(f"\n--- Cycle Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Fetch Latest Data
    # Note: In live trading, we pull the most recent 1-minute or Daily bar
    # For this POC, we check if the PDT Guard and Sanity logic are linked
    if not is_pdt_safe(): # PDT Guard from previous step
        return

    # 2. Data Sanity Check (Simulation of live bar timestamp)
    # In a real loop, you'd get this from data_client.get_stock_latest_bar()
    mock_bar_time = datetime.now(timezone.utc) # Replace with actual bar.timestamp later
    if not data_is_fresh(mock_bar_time):
        return

    print("LOGIC: Data is fresh. Risk checks passed. Ready for signal generation.")

if __name__ == "__main__":
    send_telegram_message("🤖 *Main Execution Engine Started*")
    try:
        while True:
            run_trading_cycle()
            time.sleep(60) # Wait 1 minute for the next bar
    except Exception as e:
        send_telegram_message(f"🚨 *CRITICAL ERROR:* Bot crashed! \n{e}")