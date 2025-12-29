"""
Filename: risk_manegement.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: This script prevents the bot to make more then 3 
trades on the same stock a day
Note: Under FINRA rules, if your account equity is below
$25,000, you are restricted to three day trades (buying and 
selling the same stock on the same calendar day).T 
"""

import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Initialize client in Paper mode for testing
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

"""
@brief: Checks if the account is at risk of being flagged as a Pattern Day Trader.
@return: True if it is safe to trade, False otherwise.
"""
def is_pdt_safe():
    account = trading_client.get_account()
    
    # 1. Check if already flagged
    if account.pattern_day_trader:
        print("WARNING: Account already flagged as PDT. Check equity vs $25k limit.")
        return float(account.equity) >= 25000.0

    # 2. Check rolling 5-day trade count
    # daytrade_count is an integer provided by Alpaca API
    current_count = account.daytrade_count
    
    print(f"Current 5-Day Trade Count: {current_count}")

    # We use '2' as the safety threshold to leave room for emergency exits
    if current_count >= 3:
        print("VETO: PDT Limit reached (3/3). No new entries allowed today.")
        return False
        
    return True

if __name__ == "__main__":
    # Sanity check for your account status
    safe = is_pdt_safe()
    print(f"Is account safe for new entries? {safe}")