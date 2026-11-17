"""
Filename: risk_management.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: Account-level risk checks (fail-closed).
    The old Pattern Day Trader check was removed: Alpaca retired the PDT
    fields after FINRA's intraday-margin change (June 2026).
"""

from utils.broker import trading_client

"""
@brief: Fail-closed account health check.
@return: (ok: bool, reason: str). Any missing/odd data means NOT tradable.
"""
def is_account_tradable():
    try:
        account = trading_client.get_account()
    except Exception as e:
        return False, f"account query failed: {e}"

    status = getattr(account.status, "value", str(account.status))
    if status != "ACTIVE":
        return False, f"account status is {status}, not ACTIVE"

    # 'is not False' also blocks on None/missing values
    if account.trading_blocked is not False:
        return False, f"trading_blocked is {account.trading_blocked!r}"
    if account.account_blocked is not False:
        return False, f"account_blocked is {account.account_blocked!r}"

    try:
        equity = float(account.equity)
        buying_power = float(account.buying_power)
    except (TypeError, ValueError):
        return False, "equity/buying_power missing or not numeric"

    if equity <= 0 or buying_power <= 0:
        return False, f"equity={equity}, buying_power={buying_power}"

    return True, "OK"


if __name__ == "__main__":
    print(is_account_tradable())