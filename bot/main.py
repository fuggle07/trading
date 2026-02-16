import os
import time
import asyncio
import finnhub
from flask import Flask, jsonify
from datetime import datetime
import pytz

# --- 1. INITIALIZATION ---
app = Flask(__name__)
# Crucial for Gunicorn/Cloud Run: Disable strict slashes globally or per route
app.url_map.strict_slashes = False

# Initialize Finnhub Client (Uses the secret mapped in Terraform)
FINNHUB_KEY = os.environ.get('EXCHANGE_API_KEY', 'PLACEHOLDER_INIT')
finnhub_client = finnhub.Client(api_key=FINNHUB_KEY)

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
        return finnhub_client.stock_candles(ticker, '15', start, end)

    try:
        res = await loop.run_in_executor(None, get_candles)
        if res.get('s') == 'ok':
            return res['c'][-50:]
        return []
    except Exception as e:
        print(f"❌ API Error for {ticker}: {e}")
        return []

# --- 3. THE AUDIT ENGINE ---

async def run_audit():
    """Main execution logic for the NASDAQ Node."""
    results = []
    tickers = os.environ.get("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD").split(",")
    
    print(f"🚀 Starting NASDAQ Audit for: {tickers}")

    for ticker in tickers:
        prices = await fetch_market_data(ticker)
        
        if not prices:
            results.append({"ticker": ticker, "status": "failed_data_fetch"})
            continue

        current_price = prices[-1]
        
        # This is where your ExecutionManager.log_performance() would be called
        # Example: await execution_manager.log_to_bigquery(ticker, current_price)
        
        print(f"✅ {ticker}: ${current_price:.2f}")
        results.append({
            "ticker": ticker, 
            "price": current_price, 
            "bars_analyzed": len(prices),
            "status": "logged"
        })

        # Respecting Finnhub 60/min limit
        await asyncio.sleep(1.1)

    return results

# --- 4. FLASK ROUTES ---

@app.route('/health')
def health():
    """Liveness probe for Cloud Run."""
    return "Aberfeldie Node is healthy", 200

@app.route('/run-audit', methods=['POST'])
async def run_audit_endpoint():
    """Secure endpoint triggered by Scheduler or manual curl."""
    try:
        data = await run_audit()
        return jsonify({
            "status": "complete",
            "timestamp": _get_ny_time().isoformat(),
            "results": data
        }), 200
    except Exception as e:
        print(f"🔥 Critical Failure: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 5. LOCAL RUNNER ---
if __name__ == "__main__":
    # Uses PORT env var provided by Cloud Run, defaults to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
