"""
Filename: data_downloader.py
Author:   Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created:  12-23-2025
Description: This script uses a "rolling window" approach. 
			 Used to identify of the current state of a stock is 
             HH (High High), HL (High Low), 
             LL (Low Low), LL (Low Low). 
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pandas_ta as ta

# This function is used to identify the current state of a stock
# and save its results in a database to be compared to future 
# states
def engineer_features(csv_path):
    # 1. Load the data
    df = pd.read_csv(csv_path)
    
	# --- INDICATOR CALCULATION ---
    
    # SMA 200: The "Trend Veto" - Long-term trend filter
	# (If price is below this, we don't buy)
    df['sma_200'] = ta.sma(df['close'], length=200)
    
    # Bollinger Bands: Defines "Oversold"
	# (Identifies statistically cheap prices)
    bbands = ta.bbands(df['close'], length=20, std=2)
    # pandas_ta returns columns like BBL_20_2.0 (Lower), 
	# BBM_20_2.0 (Mid), BBU_20_2.0 (Upper)
    df['bb_lower'] = bbands.iloc[:, 0] 
    
    # ATR: Used for dynamic risk management later. 
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

	# --- SWING DETECTION ---
    
    # 2. Identify Local Peaks (Highs) and Valleys (Lows)
    # We use a window of 5 days to define a 'swing'
    window = 5
    df['is_high'] = df['high'] == df['high'].rolling(window=window*2+1, center=True).max()
    df['is_low'] = df['low'] == df['low'].rolling(window=window*2+1, center=True).min()
    
    # 3. Store the values of the LAST high and LAST low to compare
    df['last_high'] = df[df['is_high']]['high'].shift(1)
    df['last_low'] = df[df['is_low']]['low'].shift(1)
    
    # Forward fill so every row knows what the 'previous' peak/valley was
    df['last_high'] = df['last_high'].ffill()
    df['last_low'] = df['last_low'].ffill()
    
    # 4. Logic for your 4 States (HH, HL, LH, LL)
    # HH: Current high > Previous high
    # HL: Current low > Previous low
    # LH: Current high < Previous high
    # LL: Current low < Previous low
    
    df['state'] = "WAIT"
    
    # We only update state when a new high or low is confirmed
    df.loc[df['is_high'] & (df['high'] > df['last_high']), 'state'] = "HH"
    df.loc[df['is_high'] & (df['high'] < df['last_high']), 'state'] = "LH"
    df.loc[df['is_low'] & (df['low'] > df['last_low']), 'state'] = "HL"
    df.loc[df['is_low'] & (df['low'] < df['last_low']), 'state'] = "LL"
    
    # --- REFINED: SIGNAL LOGIC WITH VETO ---
    df['signal_weight'] = 0.0
    
    # Filter 1: Price > SMA 200 
	# (Ensures we are in a long-term bull market) 
    # Filter 2: Price <= BB_Lower 
	# (Ensures we are buying a deep "value" dip) 
    buy_condition = (df['close'] > df['sma_200']) & (df['close'] <= df['bb_lower'])
    
    # Apply Veto: Only buy LH/LL if filters are met
    df.loc[buy_condition & (df['state'] == "LH"), 'signal_weight'] = 1.0
    df.loc[buy_condition & (df['state'] == "LL"), 'signal_weight'] = 0.5
    
    # Sell Logic: Remains same (lock in gains at any peak)
    df.loc[df['state'] == "HH", 'signal_weight'] = -1.0
    df.loc[df['state'] == "HL", 'signal_weight'] = -0.5
    
    return df

def visualize_signals(df):
    # Ensure timestamp is in datetime format for proper plotting
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
	# Setting up the plot for a better visualization
    plt.figure(figsize=(14, 8))
    plt.plot(df['timestamp'], df['close'], label='SPY Price', color='black', alpha=0.3)

    # 1. Identify where signals occur
    buys = df[df['signal_weight'] > 0]
    sells = df[df['signal_weight'] < 0]

    # 2. Plot "Buy" markers (LH and LL)
    plt.scatter(buys['timestamp'], buys['close'], 
                color='green', marker='^', s=100, label='Buy Signals (LL/LH)')

    # 3. Plot "Sell" markers (HH and HL)
    plt.scatter(sells['timestamp'], sells['close'], 
                color='red', marker='v', s=100, label='Sell Signals (HH/HL)')

    # 4. Annotate specific states (HH, LL, etc.)
    # Note: For future visualization of the script. "_" as a 	
	# 		placeholder for the index number. We just need the 
	# 		column value at "row", but we still need to eterate 
	# 		trough the index, but intentionally ignoring it.
    for _, row in df[df['state']!= "WAIT"].iterrows():
        plt.annotate(row['state'], (row['timestamp'], row['close']), 
                     textcoords="offset points", xytext=(0,10), ha='center', fontsize=9, fontweight='bold')

    plt.title('SPY Price Action Signals Audit')
    plt.xlabel('Date')
    plt.ylabel('Price ($)')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    # Save the chart to your /logs folder for the RPi record
    plt.savefig('logs/strategy_audit.png')
    print("SUCCESS: Chart saved to logs/strategy_audit.png")
    plt.show()

if __name__ == "__main__":
	processed_df = engineer_features("data/SPY_historical.csv")
#    visualize_signals(processed_df)
	print(processed_df[processed_df['signal_weight']!= 0][['timestamp', 'state', 'signal_weight']].tail(10))
    