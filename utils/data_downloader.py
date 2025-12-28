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

"""
@brief This function downloads the data for a specific data range 
and saves it with a lable in a local database so we can do our
research in real data without working with live time
@param symbol: Tells the function which stock to get the data
@param start_date: Date in which the data will start download
@param end_date: Date in which the data will end download
@param label: Name that will be used to save the data
"""
def download_custom_data(symbol, start_date, end_date, label):
    # Example: start_date = datetime(2022, 1, 1)
    print(f"--- Downloading {symbol} for {label} regime ---") 
    
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
    output_path = f"data/{symbol}_{label}.csv"
    df.to_csv(output_path, index=False)
    
    print(f"SUCCESS: {len(df)} days of data saved to {output_path}")

if __name__ == "__main__":
    # SCENARIO 1: Bear Market (SPY 2022) - S&P 500 fell ~18% this year
#    download_custom_data("SPY", datetime(2022, 1, 1), datetime(2022, 12, 31), "BEAR_2022")

    # SCENARIO 2: Different Asset (QQQ 2025) - Tech stocks often move more violently
#    download_custom_data("QQQ", datetime(2025, 1, 1), datetime(2025, 12, 20), "TECH_2025")

    # SCENARIO 3: Neutral Market (SPY 2018) - A very flat, choppy year
    download_custom_data("SPY", datetime(2018, 1, 1), datetime(2018, 12, 31), "NEUTRAL_2018")