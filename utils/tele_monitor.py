"""
Filename: data_downloader.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: This script provides a simple interface for the bot
to "talk" to me via a telegram chat. So I know what is going on 
with the bot without looking at my computer dirrectly
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    """Sends a notification to your phone via Telegram."""
    if not TOKEN or not CHAT_ID:
        print("Telegram credentials missing. Skipping alert.")
        return
        
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

if __name__ == "__main__":
    # Test alert
    send_telegram_message("*Trading Bot Online* \nStatus: Monitoring SPY")