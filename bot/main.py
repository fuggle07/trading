import os
import asyncio
import httpx
from flask import Flask, request, jsonify
# Absolute import for Cloud Run environment
from telemetry import log_performance

app = Flask(__name__)

# PILOT PHASE CONFIGURATION
# We are simulating owning 100 shares of QQQ to track alpha against the $50k hurdle
INITIAL_CASH = 50000.0
SIMULATED_TICKER = "QQQ"
SIMULATED_SHARES = 100 

async def get_live_price(ticker):
    """Fetches the current price from Finnhub API."""
    api_key = os.environ.get("FINNHUB_KEY")
    if not api_key:
        print("Error: FINNHUB_KEY not found in environment.")
        return 0.0
        
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            # 'c' is the current price in the Finnhub quote schema
            return float(data.get('c', 0))
        except Exception as e:
            print(f"Failed to fetch market data: {e}")
            return 0.0

@app.route('/run-audit', methods=['POST'])
async def run_audit():
    """
    Main execution endpoint triggered by Cloud Scheduler or Manual Curl.
    Calculates synthetic equity and logs it to BigQuery.
    """
    try:
        # 1. Fetch live market price for the pilot ticker
        current_price = await get_live_price(SIMULATED_TICKER)
        
        if current_price == 0.0:
            return jsonify({"status": "error", "message": "Market data fetch failed"}), 502

        # 2. Calculate Shadow Equity (Pilot Phase Logic)
        # We assume 100% of the $50k capital is currently in the simulated ticker
        shadow_equity = current_price * SIMULATED_SHARES
        
        # 3. Log the performance to BigQuery via telemetry module
        # This handles the 5.2% hurdle and 30% tax logic internally
        log_performance(shadow_equity)
        
        print(f"Audit Successful: {SIMULATED_TICKER} @ {current_price} | Equity: {shadow_equity}")
        
        return jsonify({
            "status": "success", 
            "paper_equity": shadow_equity, 
            "ticker": SIMULATED_TICKER,
            "price": current_price
        }), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /run-audit: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def health_check():
    return "Aberfeldie Trading Node: ONLINE", 200

if __name__ == "__main__":
    # Local dev uses port 8080 to match Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

