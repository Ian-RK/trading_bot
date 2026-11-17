"""
Filename: position_state.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 01-02-2026
Description: Converts raw reconciliation data into a strict position state.
    Anything that is not a confirmed number maps to UNKNOWN.
"""

import math
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

    # Hard failure or malformed result -> UNKNOWN
    if not isinstance(data, dict) or data.get("status") != "OK":
        return PositionState.UNKNOWN

    qty = data.get("qty")
    if isinstance(qty, bool) or not isinstance(qty, (int, float)) or not math.isfinite(qty):
        return PositionState.UNKNOWN

    if qty > 0:
        return PositionState.LONG

    if qty == 0:
        return PositionState.FLAT

    # Negative quantity (short) or anything unexpected
    return PositionState.UNKNOWN