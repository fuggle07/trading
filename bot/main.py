import os
import asyncio
import httpx
from flask import Flask, request, jsonify
from telemetry import log_performance

app = Flask(__name__)

# PILOT PHASE CONFIGURATION
INITIAL_CASH = 50000.0
SIMULATED_TICKER = "QQQ"
SIMULATED_SHARES = 100 

async def fetch_finnhub_data(symbol):
    """Generic fetcher for Finnhub quotes (Stocks or FX)."""
    api_key = os.environ.get("FINNHUB_KEY")
    if not api_key:
        return 0.0
        
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            return float(response.json().get('c', 0))
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return 0.0

@app.route('/run-audit', methods=['POST'])
async def run_audit():
    try:
        # 1. Concurrent Fetch: Get QQQ Price and AUD/USD Rate
        # FX:AUD-USD is the standard Finnhub ticker for the Aussie Dollar
        price_task = fetch_finnhub_data(SIMULATED_TICKER)
        fx_task = fetch_finnhub_data("FX:AUD-USD")
        
        current_price, aud_usd_rate = await asyncio.gather(price_task, fx_task)
        
        # Fallback if FX fetch fails (approximate 0.65 rate)
        if aud_usd_rate == 0:
            aud_usd_rate = 0.65 

        # 2. Calculate Shadow Equity
        shadow_equity = current_price * SIMULATED_SHARES
        
        # 3. Log with Live FX Rate
        # Ensure telemetry.py is updated to accept fx_rate as an argument if needed
        log_performance(shadow_equity, fx_rate_aud=aud_usd_rate)
        
        return jsonify({
            "status": "success",
            "paper_equity": shadow_equity,
            "fx_rate": aud_usd_rate,
            "ticker": SIMULATED_TICKER
        }), 200

    except Exception as e:
        print(f"Audit Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

