import os
import asyncio
import httpx
from flask import Flask, request, jsonify
from telemetry import log_performance, log_watchlist_data

app = Flask(__name__)

# PILOT PHASE CONFIGURATION
INITIAL_CASH = 50000.0
SIMULATED_TICKER = "QQQ"
SIMULATED_SHARES = 100 
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "PLTR", "ARM"]

# API URLs (Internal Services)
FINANCE_SERVICE_URL = os.getenv("FINANCE_SERVICE_URL", "http://localhost:8081")
SENTIMENT_SERVICE_URL = os.getenv("SENTIMENT_SERVICE_URL", "http://localhost:8082")

async def fetch_price_data(client, ticker):
    """Fetches price and FX data from the Finance Service."""
    url = f"{FINANCE_SERVICE_URL}/price/{ticker}"
    response = await client.get(url)
    return response.json()

async def fetch_sentiment_data(client, ticker):
    """Fetches sentiment score from the Sentiment Service."""
    url = f"{SENTIMENT_SERVICE_URL}/sentiment/{ticker}"
    response = await client.get(url)
    return response.json()

@app.route("/run", methods=["POST"])
async def run_bot():
    """Main entry point for the nightly trading logic."""
    async with httpx.AsyncClient() as client:
        # 1. Concurrent fetching of data for all tickers
        price_tasks = [fetch_price_data(client, t) for t in WATCHLIST]
        sentiment_tasks = [fetch_sentiment_data(client, t) for t in WATCHLIST]
        
        prices = await asyncio.gather(*price_tasks)
        sentiments = await asyncio.gather(*sentiment_tasks)
        
        # 2. Process results into a watchlist
        watchlist_rows = []
        for i, ticker in enumerate(WATCHLIST):
            watchlist_rows.append({
                "ticker": ticker,
                "price": prices[i].get("price"),
                "fx_rate": prices[i].get("fx_rate"),
                "sentiment_score": sentiments[i].get("score"),
                "timestamp": sentiments[i].get("timestamp")
            })

        # 3. Simulated 'Pilot' Trade (Fixed Logic for now)
        # In a real scenario, we'd loop through sentiments and pick the highest score
        target_ticker = SIMULATED_TICKER
        sentiment_score = next((s["score"] for i, s in enumerate(sentiments) if WATCHLIST[i] == target_ticker), 0)
        
        # 4. Telemetry: Log the data to BigQuery
        log_watchlist_data(watchlist_rows)
        
        # Log performance (Simulated)
        log_performance({
            "ticker": target_ticker,
            "action": "BUY" if sentiment_score > 0.5 else "HOLD",
            "shares": SIMULATED_SHARES,
            "cash_remaining": INITIAL_CASH - (prices[0].get("price") * SIMULATED_SHARES)
        })

        return jsonify({
            "status": "success",
            "processed_tickers": len(WATCHLIST),
            "pilot_trade": target_ticker
        }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

