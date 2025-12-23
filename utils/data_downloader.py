"""
Filename: data_downloader.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-23-2025
Description: This script uses the alpaca-py library to fetch
             "Bars" (Open, High, Low, Close, Volume data).
"""

import os
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

# 1. Load credentials
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# 2. Initialize the Client
client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# This function downloads the data from the Stock history
# and store the data in a local database so we can do our
# research in real data without working with live time
def download_data(symbol, days=365):
    print(f"--- Fetching data for {symbol} ---")
    
    # Define time range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 3. Create the Request
    request_params = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start_date,
        end=end_date
    )
    
    # 4. Execute Fetch
    bars = client.get_stock_bars(request_params)
    
    # 5. Convert to Pandas DataFrame
    df = bars.df
    
    # 6. Save to /data folder
    # Note: df index is a multi-index (symbol, timestamp). We'll reset it.
    df = df.reset_index()
    output_path = f"data/{symbol}_historical.csv"
    df.to_csv(output_path, index=False)
    
    print(f"SUCCESS: {len(df)} days of data saved to {output_path}")
    return df

if __name__ == "__main__":
    download_data("SPY")