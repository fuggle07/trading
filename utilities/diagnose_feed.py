"""
Finnhub Feed Diagnosis Utility
Usage: python3 utilities/diagnose_feed.py
Description: Tests Finnhub API connectivity and data freshness for a sample ticker (NVDA).
"""
#!/usr/bin/env python3
import sys
import os

# Ensure the project root is in the path so we can import 'bot'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import finnhub
import os
import time
import datetime
import pandas as pd

def diagnose():
    api_key = os.environ.get("EXCHANGE_API_KEY")
    if not api_key:
        print("❌ EXCHANGE_API_KEY not found.")
        return

    print(f"🔑 Using API Key: {api_key[:4]}...{api_key[-4:]}")
    client = finnhub.Client(api_key=api_key)

    ticker = "NVDA"
    print(f"👉 Requesting data for {ticker}...")

    # 1. Test Basic Quote (Current Price)
    try:
        quote = client.quote(ticker)
        print(f"✅ Quote: {quote}")
    except Exception as e:
        print(f"❌ Quote Failed: {e}")

    # 2. Test Candles (Historical)
    try:
        # Mimic main.py logic
        end = int(time.time())
        start = end - (70 * 24 * 60 * 60)
        res = client.stock_candles(ticker, "D", start, end)

        if res.get("s") == "ok":
            print("✅ API Response: OK")
            df = pd.DataFrame(res)
            # Convert t to datetime
            df["t"] = pd.to_datetime(df["t"], unit="s")

            last_row = df.iloc[-1]
            print(f"📊 Last Candle Timestamp: {last_row['t']}")
            print(f"📊 Last Close Price: {last_row['c']}")

            # Check if it's "fresh"
            now = datetime.datetime.now()
            diff = now - last_row["t"]
            print(f"🕒 Time since last candle: {diff}")

            if diff.days > 2:
                print(
                    "⚠️ Data is stale (> 2 days). Market might be closed or feed delayed."
                )
            elif diff.days < 1:
                print("✅ Data is fresh (within 24h).")
            else:
                print("ℹ️ Data is from the weekend/holiday.")

        else:
            print(f"❌ API Response Error: {res}")

    except Exception as e:
        print(f"🔥 Exception: {e}")

if __name__ == "__main__":
    diagnose()
