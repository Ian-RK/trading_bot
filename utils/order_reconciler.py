"""
Filename: order_reconciler.py
Description: Read-only query of open orders for a symbol.
    Alpaca is the source of truth. Places and cancels nothing.
"""

from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from utils.position_reconciler import trading_client


def get_open_orders(symbol: str):
    """
    Returns {"status": "OK", "count": int, "orders": [...]} on success,
    or {"status": "ERROR", "count": None, "orders": None} on ANY failure.
    A failed query must never be read as "no open orders".
    """
    try:
        request = GetOrdersRequest(
            status=QueryOrderStatus.OPEN,
            symbols=[symbol],
            limit=50,
        )
        raw_orders = trading_client.get_orders(filter=request)

        orders = []
        for o in raw_orders:
            orders.append({
                "id": str(o.id),
                "side": getattr(o.side, "value", str(o.side)),
                "qty": str(o.qty),
                "type": getattr(o.order_type, "value", str(o.order_type)),
                "status": getattr(o.status, "value", str(o.status)),
                "submitted_at": str(o.submitted_at),
            })
    except Exception as e:
        print(f"[ORDER RECONCILE ERROR] Failed to fetch open orders: {e}")
        return {"status": "ERROR", "count": None, "orders": None}

    return {"status": "OK", "count": len(orders), "orders": orders}