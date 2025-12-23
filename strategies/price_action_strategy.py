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

def engineer_features(csv_path):
    # 1. Load the data
    df = pd.read_csv(csv_path)
    
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
    
    # 5. Mapping your custom Scaling Logic
    # Mapping: HH -> Sell Lot (-1.0), HL -> Sell Little (-0.5), 
    #          LL -> Buy Little (0.5), LH -> Buy Lot (1.0)
    #          WAIT -> (0.0)
    weights = {"HH": -1.0, "HL": -0.5, 
               "LL": 0.5, "LH": 1.0, "WAIT": 0.0}
    df['signal_weight'] = df['state'].map(weights)
    
    return df

if __name__ == "__main__":
    processed_df = engineer_features("data/SPY_historical.csv")
    
    # Print the last few confirmed signals
    print(processed_df[processed_df['state']!= "WAIT"][['timestamp', 'state', 'signal_weight']].tail(10))