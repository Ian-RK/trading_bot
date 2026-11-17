"""
Filename: position_reconciler.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 01-02-2026
Description: Read-only reconciliation with Alpaca.
    The exchange is the single source of truth.
    On ANY error, qty / market_value / exists are None (never 0.0),
    so a failed query can never be mistaken for a flat position.
"""

import math

from utils.broker import trading_client


def _error(reason):
    print(f"[RECONCILE ERROR] {reason}")
    return {
        "exists": None,
        "qty": None,
        "market_value": None,
        "side": None,
        "status": "ERROR",
    }


def get_current_position(symbol: str):
    """
    Returns a dict with keys: exists, qty, market_value, side, status.
    status == "OK"    -> qty/market_value are real numbers (0.0 means confirmed flat).
    status == "ERROR" -> qty/market_value/exists are None. Never treat as flat.
    """
    try:
        positions = trading_client.get_all_positions()

        for p in positions:
            if p.symbol == symbol:
                qty = float(p.qty)
                market_value = float(p.market_value)

                if not (math.isfinite(qty) and math.isfinite(market_value)):
                    return _error("Position has a non-finite qty or market value")

                if qty > 0:
                    side = "LONG"
                elif qty < 0:
                    side = "SHORT"
                else:
                    side = None

                return {
                    "exists": qty != 0,
                    "qty": qty,
                    "market_value": market_value,
                    "side": side,
                    "status": "OK",
                }
    except Exception as e:
        detail = " ".join(str(e).split())[:200]
        return _error(f"Failed to fetch/parse positions: {detail}")

    # Query succeeded and no position exists for this symbol
    return {
        "exists": False,
        "qty": 0.0,
        "market_value": 0.0,
        "side": None,
        "status": "OK",
    }