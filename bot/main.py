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

async def fetch_finnhub_data(endpoint, params):
    """Generic fetcher for Finnhub REST endpoints."""
    api_key = os.environ.get("FINNHUB_KEY")
    url = f"https://finnhub.io/api/v1/{endpoint}"
    params['token'] = api_key
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            return response.json()
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            return {}

@app.route('/run-audit', methods=['POST'])
async def run_audit():
    try:
        # 1. Concurrent Fetch: Price, FX, and Sentiment
        price_task = fetch_finnhub_data("quote", {"symbol": SIMULATED_TICKER})
        fx_task = fetch_finnhub_data("quote", {"symbol": "FX:AUD-USD"})
        sentiment_task = fetch_finnhub_data("stock/social-sentiment", {"symbol": SIMULATED_TICKER})
        
        price_data, fx_data, sentiment_data = await asyncio.gather(
            price_task, fx_task, sentiment_task
        )
        
        # 2. Extract Metrics
        current_price = float(price_data.get('c', 0))
        aud_usd_rate = float(fx_data.get('c', 0.65))
        
        # Extract Reddit/Twitter sentiment (Average of the two for the bot)
        # Finnhub returns lists for reddit and twitter; we take the most recent entry
        reddit = sentiment_data.get('reddit', [{}])[-1]
        twitter = sentiment_data.get('twitter', [{}])[-1]
        
        avg_sentiment = (reddit.get('sentiment', 0.5) + twitter.get('sentiment', 0.5)) / 2
        mention_volume = reddit.get('mention', 0) + twitter.get('mention', 0)

        # 3. Calculate Shadow Equity
        shadow_equity = current_price * SIMULATED_SHARES
        
        # 4. Log to BigQuery
        # Note: You may need to add 'sentiment' and 'volume' columns to your BigQuery table
        log_performance(
            paper_equity=shadow_equity, 
            fx_rate_aud=aud_usd_rate,
            sentiment_score=avg_sentiment,
            social_volume=mention_volume
        )
        
        return jsonify({
            "status": "success",
            "equity": shadow_equity,
            "sentiment": avg_sentiment,
            "volume": mention_volume
        }), 200

        # 5. Process Watchlist
        watchlist_tasks = [fetch_finnhub_data("quote", {"symbol": t}) for t in WATCHLIST]
        watchlist_results = await asyncio.gather(*watchlist_tasks)

        for i, data in enumerate(watchlist_results):
            ticker = WATCHLIST[i]
            price = float(data.get('c', 0))
            if price > 0:
                # Log these to the new watchlist_logs table
                log_watchlist_data(ticker, price)

        return jsonify({"status": "success", "watchlist_updated": len(WATCHLIST)}), 200

    except Exception as e:
        print(f"Audit Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

