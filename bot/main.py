import os
import time
import asyncio
import finnhub
from flask import Flask, jsonify
from datetime import datetime, timezone
from telemetry import log_watchlist_data
import pytz
from google.cloud import bigquery


# --- 1. INITIALIZATION ---
app = Flask(__name__)
app.url_map.strict_slashes = False

# Retrieve the key with a clear fallback for checking
FINNHUB_KEY = os.environ.get('EXCHANGE_API_KEY')

def check_api_key():
    """Validates that the API key is present and not a placeholder."""
    if not FINNHUB_KEY or len(FINNHUB_KEY) < 10: # Simple length check
        return False
    return True

# Initialize client only if key exists, or handle it in the route
finnhub_client = finnhub.Client(api_key=FINNHUB_KEY) if FINNHUB_KEY else None

# Initialize BigQuery Client
PROJECT_ID = os.environ.get('PROJECT_ID', 'trading-12345') # Fallback for local dev
bq_client = bigquery.Client(project=PROJECT_ID)
table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"

# --- 2. CORE UTILITIES ---

def _get_ny_time():
    return datetime.now(pytz.timezone('America/New_York'))

async def fetch_market_data(ticker):
    """Wraps synchronous Finnhub SDK in an executor for thread-safety."""
    loop = asyncio.get_event_loop()
    
    def get_candles():
        end = int(time.time())
        # Fetch 7 days to guarantee 50 periods even after weekends/holidays
        start = end - (7 * 24 * 60 * 60)
        if not finnhub_client:
            print(f"⚠️  WARNING: Finnhub client not initialized (missing key). Skipping {ticker}")
            return None
        return finnhub_client.stock_candles(ticker, '15', start, end)

    try:
        res = await loop.run_in_executor(None, get_candles)
        if res and res.get('s') == 'ok':
            return res['c'][-50:]
        return []
    except Exception as e:
        print(f"❌ API Error for {ticker}: {e}")
        return []

# --- 3. THE AUDIT ENGINE ---

async def run_audit():
    results = []
    tickers_env = os.environ.get("BASE_TICKERS", "NVDA,AAPL")
    tickers = [t.strip() for t in tickers_env.split(",") if t.strip()]
    print(f"🔍 DEBUG: Bot is attempting to audit these specific tickers: {tickers}")
    
    for ticker in tickers:
        prices = await fetch_market_data(ticker)
        if prices:
            current_price = prices[-1]
            # Call your telemetry function to actually write to BQ
            log_watchlist_data(bq_client, table_id, ticker, current_price) 
            results.append({"ticker": ticker, "price": current_price, "status": "logged"})
        await asyncio.sleep(1.1)
    return results

# --- 4. FLASK ROUTES ---

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/run-audit', methods=['POST'])
async def run_audit_endpoint():
    # 1. Immediate Key Validation
    if not check_api_key():
        error_msg = "❌ EXCHANGE_API_KEY is missing or invalid in Secret Manager."
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 401

    try:
        data = await run_audit()

        # 2. Check if results are empty because of API rejection
        if not data:
            return jsonify({
                "status": "warning",
                "message": "No data returned. Check if API Key is active or Tickers are correct."
            }), 200

        return jsonify({
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": data
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 5. LOCAL RUNNER ---
if __name__ == "__main__":
    # Uses PORT env var provided by Cloud Run, defaults to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
