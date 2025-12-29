"""
Filename: execution_agent.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-27-2025
Description: This script will keep the execution logic modular.
This script calculates your current buying power and translates
the signal_weight into a specific number of shares.
"""

import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv

load_dotenv()
trading_client = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)

def execute_weighted_trade(symbol, weight, current_price):
    """
    Translates strategy weights into actual Paper orders.
    weight: 1.0 (Buy All), 0.5 (Buy Little), -1.0 (Sell All)
    """
    account = trading_client.get_account()
    equity = float(account.equity)
    
    # Calculate target dollar value for the position
    # If weight is positive, we want exposure (e.g., 100% or 50% of equity)
    # If weight is negative, we reduce/exit
    target_pct = weight if weight > 0 else (1.0 + weight)
    target_value = equity * target_pct
    
    # Check current position to see how many shares we need to add/remove
    positions = trading_client.get_all_positions()
    current_qty = 0
    for p in positions:
        if p.symbol == symbol:
            current_qty = float(p.qty)
            break
            
    current_market_value = current_qty * current_price
    diff_dollars = target_value - current_market_value
    shares_to_trade = int(diff_dollars / current_price)

    if shares_to_trade == 0:
        return None

    # Define Side
    side = OrderSide.BUY if shares_to_trade > 0 else OrderSide.SELL
    
    # Prepare the Order Object
    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=abs(shares_to_trade),
        side=side,
        time_in_force=TimeInForce.DAY
    )
    
    # Submit to Alpaca Paper
    order = trading_client.submit_order(order_data=order_data)
    return order