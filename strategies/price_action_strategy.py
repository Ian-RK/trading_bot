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

"""
@brief This function is used to identify the current state of a stock
and save its results in a database to be compared to future states
@param csv_path path to the data downloaded by data_download.py
@return df the loaded data saved in pandas format
"""
def calculate_signals(df):
    # 1. Ensure data is clean
    df = df.copy()
    
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
    
        # 2. Identify swing highs/lows CAUSALLY.
    # A swing at row t needs rows t-5..t+5 (centered 11-row window), so it is
    # only KNOWN at row t+5. Detect it on the centered window, then shift the
    # flag and the pivot price forward by `window` rows: row i uses rows 0..i only.
    window = 5
    window_size = window * 2 + 1
    raw_high = df['high'] == df['high'].rolling(window=window_size, center=True).max()
    raw_low = df['low'] == df['low'].rolling(window=window_size, center=True).min()
    df['is_high'] = raw_high.shift(window, fill_value=False)
    df['is_low'] = raw_low.shift(window, fill_value=False)
    pivot_high = df['high'].shift(window)    # the pivot's own high, known at confirm row
    pivot_low = df['low'].shift(window)

    # 3. Previous confirmed pivot values, forward-filled
    df['last_high'] = pivot_high[df['is_high']].shift(1)
    df['last_low'] = pivot_low[df['is_low']].shift(1)
    df['last_high'] = df['last_high'].ffill()
    df['last_low'] = df['last_low'].ffill()

    # 4. States (HH, HL, LH, LL), set only when a pivot is confirmed
    df['state'] = "WAIT"
    df.loc[df['is_high'] & (pivot_high > df['last_high']), 'state'] = "HH"
    df.loc[df['is_high'] & (pivot_high < df['last_high']), 'state'] = "LH"
    df.loc[df['is_low'] & (pivot_low > df['last_low']), 'state'] = "HL"
    df.loc[df['is_low'] & (pivot_low < df['last_low']), 'state'] = "LL"
    
    # --- SIGNAL LOGIC WITH VETO ---
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

def engineer_features(df_or_path):
    """
    Unified entry point. 
    Accepts a string (file path) or a pandas DataFrame.
    """
    if isinstance(df_or_path, str):
        df = pd.read_csv(df_or_path)
    else:
        df = df_or_path
        
    return calculate_signals(df)

"""
@brief Method created to vizualize the signals in a graphing 
format Buy singnals are in green and Sell signals are in red
@param df the updated data saved in pandas format
"""
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
    