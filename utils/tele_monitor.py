"""
Filename: tele_monitor.py
Author: Ian Rodrigues Kmiliauskis (iankmiliauskis1604@gmail.com)
Created: 12-26-2025
Description: This script provides a simple interface for the bot
to "talk" to me via a telegram chat. So I know what is going on
with the bot without looking at my computer directly.
Failures never print the request URL (it contains the bot token).
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _redact(text):
    """One line, at most 200 chars, token removed."""
    text = " ".join(str(text).split())
    if TOKEN:
        text = text.replace(TOKEN, "<redacted>")
    return text[:200]


def send_telegram_message(message):
    """
    Sends a notification to your phone via Telegram (HTML parse mode).
    Returns True if sent, False otherwise. Never raises, never prints the token.
    """
    if not TOKEN or not CHAT_ID:
        print("Telegram credentials missing. Skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        resp = getattr(e, "response", None)
        status = getattr(resp, "status_code", "unknown")
        detail = ""
        try:
            detail = f" - {_redact(resp.json().get('description', ''))}"
        except Exception:
            pass
        print(f"Failed to send Telegram message: HTTP {status}{detail}")
    except Exception as e:
        # Only the error TYPE: the message text may contain the URL.
        print(f"Failed to send Telegram message: {type(e).__name__}")
    return False


if __name__ == "__main__":
    # Test alert
    send_telegram_message("<b>Trading Bot Online</b> \nStatus: Monitoring SPY")