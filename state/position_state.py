"""
Filename: position_state.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 01-02-2026
Description: Converts raw reconciliation data into a strict position state.
"""

from enum import Enum
from utils.position_reconciler import get_current_position


class PositionState(Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    UNKNOWN = "UNKNOWN"


def determine_position_state(symbol: str) -> PositionState:
    """
    Determines the current position state using Alpaca as source of truth.
    """
    data = get_current_position(symbol)

    # Hard failure → UNKNOWN
    if data.get("status") != "OK":
        return PositionState.UNKNOWN

    # Defensive checks
    qty = data.get("qty", 0.0)

    if qty > 0:
        return PositionState.LONG

    if qty == 0:
        return PositionState.FLAT

    # Any unexpected condition
    return PositionState.UNKNOWN
