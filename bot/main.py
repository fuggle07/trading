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
WATCHLIST = ["NVDA", "TSLA", "AAPL", "MSFT"]

async def fetch_finnhub_data(endpoint, params):
    """Generic fetcher for Finnhub REST endpoints."""
    api_key = os.environ.get("FINNHUB_KEY")
    if not api_key:
        print("CRITICAL: FINNHUB_KEY not found in environment.")
        return {}
        
    url = f"https://finnhub.io/api/v1/{endpoint}"
    params['token'] = api_key
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code == 429:
                print("WARNING: Finnhub Rate Limit Hit (429). Throttling required.")
                return {}
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching {endpoint} for {params.get('symbol')}: {e}")
            return {}

@app.route('/run-audit', methods=['POST'])
async def run_audit():
    """
    Main execution endpoint. Fetches price, FX, and sentiment sequentially
    to respect Finnhub's 60 calls/minute limit.
    """
    try:
        # 1. Fetch Primary Performance Data (QQQ + FX)
        price_data = await fetch_finnhub_data("quote", {"symbol": SIMULATED_TICKER})
        await asyncio.sleep(1.1) # Rate limiting delay
        
        fx_data = await fetch_finnhub_data("quote", {"symbol": "FX:AUD-USD"})
        await asyncio.sleep(1.1)
        
        # 2. Fetch QQQ Social Sentiment
        sentiment_data = await fetch_finnhub_data("stock/social-sentiment", {"symbol": SIMULATED_TICKER})
        
        # Extract Core Metrics
        current_price = float(price_data.get('c', 0))
        aud_usd_rate = float(fx_data.get('c', 0.65))
        
        # Parse Sentiment
        reddit = sentiment_data.get('reddit', [{}])[-1]
        twitter = sentiment_data.get('twitter', [{}])[-1]
        avg_sentiment = (reddit.get('sentiment', 0.5) + twitter.get('sentiment', 0.5)) / 2
        mention_vol = reddit.get('mention', 0) + twitter.get('mention', 0)

        # 3. Log Performance (The "Aberfeldie Alpha")
        shadow_equity = current_price * SIMULATED_SHARES
        log_performance(
            paper_equity=shadow_equity, 
            fx_rate_aud=aud_usd_rate,
            sentiment_score=avg_sentiment,
            social_volume=mention_vol
        )

        # 4. Process Watchlist Serially
        watchlist_count = 0
        for ticker in WATCHLIST:
            await asyncio.sleep(1.1) # Essential delay for free tier
            w_data = await fetch_finnhub_data("quote", {"symbol": ticker})
            w_price = float(w_data.get('c', 0))
            
            if w_price > 0:
                log_watchlist_data(ticker, w_price)
                watchlist_count += 1

        print(f"Successfully logged Audit and {watchlist_count} watchlist stocks.")
        return jsonify({
            "status": "success",
            "paper_equity": shadow_equity,
            "watchlist_processed": watchlist_count
        }), 200

    except Exception as e:
        print(f"CRITICAL ERROR in /run-audit: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def health_check():
    return "Aberfeldie Trading Node: ONLINE", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

