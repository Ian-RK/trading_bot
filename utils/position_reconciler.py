"""
Filename: position_reconciler.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 01-02-2026
Description: Read-only reconciliation with Alpaca.
    		 The exchange is the single source of truth.
"""

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os

load_dotenv()

trading_client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True
)

def get_current_position(symbol: str):
    """
    Queries Alpaca for the current position in `symbol`.

    Returns a dict with explicit, defensive fields.
    """
    try:
        positions = trading_client.get_all_positions()
    except Exception as e:
        print(f"[RECONCILE ERROR] Failed to fetch positions: {e}")
        return {
            "exists": False,
            "qty": 0.0,
            "market_value": 0.0,
            "side": None,
            "status": "ERROR"
        }

    for p in positions:
        if p.symbol == symbol:
            qty = float(p.qty)
            return {
                "exists": qty != 0,
                "qty": qty,
                "market_value": float(p.market_value),
                "side": "LONG" if qty > 0 else None,
                "status": "OK"
            }

    # No position found
    return {
        "exists": False,
        "qty": 0.0,
        "market_value": 0.0,
        "side": None,
        "status": "OK"
    }
