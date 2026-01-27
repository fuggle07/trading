# verification.py - Hard Proof Engine with Resilience
import os
import time
import finnhub
from datetime import datetime, timedelta

def get_hard_proof(ticker):
    """
    Surgical Verification of Insider Conviction & Disclosure Velocity.
    Implements retry logic for rate-limit resilience.
    """
    api_key = os.getenv("FINNHUB_KEY")
    client = finnhub.Client(api_key=api_key)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

    # Retry Loop for 429 Resilience
    for attempt in range(3):
        try:
            # 1. Insider MSPR (Conviction)
            insider_data = client.stock_insider_sentiment(ticker, start_date, end_date)
            mspr_sum = sum(item['mspr'] for item in insider_data.get('data', []))

            # 2. SEC Velocity (Event Frequency)
            filings = client.filings(symbol=ticker, _from=start_date, to=end_date)
            filing_velocity = len([f for f in filings if f['form'] in ['8-K', '4']])

            # 3. Decision Logic
            if mspr_sum > 0 and filing_velocity > 0:
                return (mspr_sum / 10) + filing_velocity
            return -1.0 if mspr_sum < -50 else 0.0

        except Exception as e:
            if "429" in str(e):
                wait = 2 ** (attempt + 1)
                print(f"⚠️  Rate limit hit for {ticker}. Backing off {wait}s...")
                time.sleep(wait)
            else:
                print(f"❌ Verification Error [{ticker}]: {e}")
                return 0
    return 0

