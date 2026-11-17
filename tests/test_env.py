import os
from dotenv import load_dotenv

# Load the variables from.env
load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
base_url = os.getenv("ALPACA_BASE_URL")

if api_key:
    print(f"SUCCESS: Environment variables loaded.")
    print(f"Targeting: {base_url}")
else:
    print("ERROR: Could not find ALPACA_API_KEY. Check your.env file.")