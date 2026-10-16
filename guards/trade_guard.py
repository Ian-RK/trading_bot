"""
Filename: trade_guard.py
Author: Ian Rodrigues Kmiliauskis
Description:
    Enforces trade safety based on current position state.
"""

from enum import Enum
from state.position_state import PositionState


class TradeAction(Enum):
    BUY = "BUY"
    SELL = "SELL"


def is_trade_allowed(
    position_state: PositionState,
    action: TradeAction
) -> bool:
    """
    Determines whether a trade is allowed given the position state.
    """
    if position_state == PositionState.UNKNOWN:
        return False

    if position_state == PositionState.FLAT:
        return action == TradeAction.BUY

    if position_state == PositionState.LONG:
        return action == TradeAction.SELL

    return False
