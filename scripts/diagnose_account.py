"""
Read-only account diagnostic. Places no orders.
Prints the account fields the risk checks depend on.
"""
from utils.position_reconciler import trading_client

account = trading_client.get_account()

# Show only a short prefix of the account number
acct_no = str(account.account_number)
print("account_number prefix:", acct_no[:2] + "***")

fields = [
    "status",
    "pattern_day_trader",
    "daytrade_count",
    "equity",
    "buying_power",
    "multiplier",
    "trading_blocked",
    "account_blocked",
    "shorting_enabled",
]
for field in fields:
    print(f"{field}: {getattr(account, field, 'MISSING')!r}")