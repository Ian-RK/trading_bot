"""
Filename: data_downloader.py
Author:   Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created:  12-23-2025
Description: This script implements a "Market Realism" layer. 
			 It assumes 0.1% slippage (you get a slightly worse 
             price than the "Close") and a small commission per share.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from strategies.price_action_strategy import engineer_features

# --- 1. SETTINGS ---
INITIAL_CAPITAL = 10000.0
COMMISSION_PER_SHARE = 0.01  # Typical broker fee
SLIPPAGE_PCT = 0.001         # 0.1% market impact cost

def run_backtest(df):
    cash = INITIAL_CAPITAL
    shares = 0
    equity_curve = []

    print(f"--- Starting Backtest with ${INITIAL_CAPITAL} ---")

    for i, row in df.iterrows():
        current_price = row['close']
        weight = row['signal_weight']
        
        # 2. TRADE EXECUTION LOGIC
        # if is not  in a WAIT state do something
        if weight!= 0:
            # Calculate Target Position in Dollars
            # 1.0 (Buy Lot) -> 100% of Total Equity
            # 0.5 (Buy Little) -> 50% of Total Equity
            # -1.0 (Sell Lot) -> 0% (Liquidate)
            # -0.5 (Sell Little) -> 50% (Reduce)
            
            current_total_value = cash + (shares * current_price)
            target_pct = weight if weight > 0 else (1.0 + weight)
            target_value = current_total_value * target_pct
            
            # Apply Slippage: Buy slightly higher, Sell slightly lower [3]
            execution_price = current_price * (1 + SLIPPAGE_PCT) if weight > 0 else current_price * (1 - SLIPPAGE_PCT)
            
            # Calculate difference between current holdings and target
            diff_dollars = target_value - (shares * execution_price)
            shares_to_trade = int(diff_dollars / execution_price)
            
            if shares_to_trade!= 0:
                cost = shares_to_trade * execution_price
                commissions = abs(shares_to_trade) * COMMISSION_PER_SHARE
                cash -= (cost + commissions)
                shares += shares_to_trade
                
                # FIXED: trade_type is now used in the debug log
                trade_type = "BUY" if shares_to_trade > 0 else "SELL"
                print(f"Day {i}: {trade_type} {abs(shares_to_trade)} shares @ ${execution_price:.2f}")

        # 3. END OF DAY VALUATIONS
        daily_equity = cash + (shares * current_price)
        equity_curve.append(daily_equity)

    df['total_equity'] = equity_curve
    return df

# --- 4. PERFORMANCE METRICS --- 
def print_metrics(df):
    # iloc[-1]: Finds the final value of your total_equity column
	# 			on the very last day of the year.
    total_return = (df['total_equity'].iloc[-1] / 
                    INITIAL_CAPITAL - 1) * 100
    
    # Calculate Drawdown
    # .cummax(): Calculates the Cumulative Maximum
    rolling_max = df['total_equity'].cummax()
    drawdown = (df['total_equity'] / rolling_max - 1)
    max_drawdown = drawdown.min() * 100
    
    # Sharpe Ratio (Simplified Annualized)
    # .pct_change(): Calculates the fractional change between the 
	# 				 curr row and the one immediately before it.
    # .dropna(): Removes empty rows so we can calculate a 
	# 			 clean Sharpe Ratio.
    daily_returns = df['total_equity'].pct_change().dropna()
    sharpe = np.sqrt(252) * daily_returns.mean() / daily_returns.std() if daily_returns.std()!= 0 else 0

    print(f"\nBACKTEST RESULTS:")
    print(f"Final Equity: ${df['total_equity'].iloc[-1]:.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")

if __name__ == "__main__":
    data = engineer_features("data/SPY_historical.csv")
    results = run_backtest(data)
    print_metrics(results)
    
    results.plot(x='timestamp', y='total_equity', 
                 title='Account Balance Over Time')
    plt.savefig('logs/backtest_equity_curve.png')
    plt.show()