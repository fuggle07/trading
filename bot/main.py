import os
import time
import asyncio
import finnhub
import pandas as pd
from flask import Flask, jsonify
from datetime import datetime, timezone, timedelta
from telemetry import log_watchlist_data
import pytz
from google.cloud import bigquery
from signal_agent import SignalAgent
from execution_manager import ExecutionManager
from portfolio_manager import PortfolioManager

# --- 1. INITIALIZATION ---
app = Flask(__name__)
app.url_map.strict_slashes = False

# Retrieve the key
FINNHUB_KEY = os.environ.get('EXCHANGE_API_KEY')

def check_api_key():
    """Validates that the API key is present."""
    if not FINNHUB_KEY or len(FINNHUB_KEY) < 10:
        return False
    return True

# Initialize Clients
finnhub_client = finnhub.Client(api_key=FINNHUB_KEY) if FINNHUB_KEY else None

# Initialize BigQuery Client
PROJECT_ID = os.environ.get('PROJECT_ID', 'trading-12345')
bq_client = bigquery.Client(project=PROJECT_ID)
table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"
portfolio_table_id = f"{PROJECT_ID}.trading_data.portfolio"

# Initialize Trading Agents
# specific risk/vol settings can be loaded from env if needed
signal_agent = SignalAgent() 
portfolio_manager = PortfolioManager(bq_client, portfolio_table_id)
execution_manager = ExecutionManager(portfolio_manager)

# --- 2. CORE UTILITIES ---

def _get_ny_time():
    return datetime.now(pytz.timezone('America/New_York'))

async def fetch_historical_data(ticker):
    """Fetches daily candles for the last 60 days to support SMA-50 calculation."""
    loop = asyncio.get_event_loop()
    
    def get_candles():
        if not finnhub_client:
            return None
        
        # We need ~60 days of data for SMA-50. 
        # Adding a buffer to 70 days.
        end = int(time.time())
        start = end - (70 * 24 * 60 * 60)
        
        # Resolution 'D' = Daily
        return finnhub_client.stock_candles(ticker, 'D', start, end)

    try:
        res = await loop.run_in_executor(None, get_candles)
        
        if res and res.get('s') == 'ok':
            # Create DataFrame
            df = pd.DataFrame({
                't': res['t'],
                'c': res['c'],
                'h': res['h'],
                'l': res['l'],
                'o': res['o'],
                'v': res['v']
            })
            # Convert timestamp to datetime
            df['t'] = pd.to_datetime(df['t'], unit='s')
            return df
            
        print(f"⚠️  Finnhub returned no candle data for {ticker}. Response: {res}")
        return None
    except Exception as e:
        print(f"❌ API Error for {ticker}: {e}")
        return None

def calculate_technical_indicators(df):
    """Calculates SMA-20, SMA-50, and Bollinger Bands."""
    if df is None or len(df) < 50:
        return None

    # Calculate SMAs
    df['sma_20'] = df['c'].rolling(window=20).mean()
    df['sma_50'] = df['c'].rolling(window=50).mean()

    # Calculate Bollinger Bands (20-day, 2 std dev)
    rolling_std = df['c'].rolling(window=20).std()
    df['bb_upper'] = df['sma_20'] + (rolling_std * 2)
    df['bb_lower'] = df['sma_20'] - (rolling_std * 2)

    # Return the latest slice as a dictionary for the strategy
    latest = df.iloc[-1]
    
    # Ensure no NaN values in the latest slice (can happen if data is too short)
    if pd.isna(latest['sma_50']):
        return None

    return {
        "current_price": latest['c'],
        "sma_20": latest['sma_20'],
        "sma_50": latest['sma_50'],
        "bb_upper": latest['bb_upper'],
        "bb_lower": latest['bb_lower'],
        "timestamp": latest['t']
    }

# --- 3. THE AUDIT ENGINE ---

def fetch_sentiment(ticker):
    """Fetches news sentiment score from Finnhub (0-1 score, or -1 to 1)."""
    # Note: Finnhub 'news-sentiment' endpoint returns detailed data.
    # We will use the 'sentiment' score if available, or 'buzz'.
    # Free tier might define this differently, so we wrap safely.
    if not finnhub_client: 
        return None
        
    try:
        # Get News Sentiment
        res = finnhub_client.news_sentiment(ticker)
        # Structure: {'sentiment': {'bearishPercent': 0.1, 'bullishPercent': 0.8}, 'sectorAverageBullishPercent': ...}
        # Actually Finnhub's News Sentiment endpoint structure varies.
        # Let's try 'news_sentiment' and see if we get a 'buzz' or 'sentiment' object.
        # Typically: res['sentiment'] object exists.
        
        if res and 'sentiment' in res:
             # Calculate a simple score: Bullish - Bearish
             bullish = res['sentiment'].get('bullishPercent', 0.5)
             bearish = res['sentiment'].get('bearishPercent', 0.5)
             
             # Score from -1 (Bearish) to +1 (Bullish)
             score = bullish - bearish
             return score
             
        return 0.0 # Neutral default if no data
    except Exception as e:
        print(f"⚠️  Sentiment fetch failed for {ticker}: {e}")
        return None

# --- 3. THE AUDIT ENGINE ---

async def run_audit():
    results = []
    tickers_env = os.environ.get("BASE_TICKERS", "NVDA,AAPL")
    tickers = [t.strip() for t in tickers_env.split(",") if t.strip()]
    print(f"🔍 DEBUG: Bot is attempting to audit tickers: {tickers}")
    
    # Track latest prices for portfolio valuation
    current_prices = {}

    for ticker in tickers:
        print(f"👉 Processing {ticker}...")
        
        # 0. Ensure Portfolio State (Seed if new)
        try:
            # We run this synchronously to ensure state relies on it
            # In production, cache this check
            await asyncio.to_thread(portfolio_manager.ensure_portfolio_state, ticker)
        except Exception as e:
            print(f"⚠️ Portfolio Init Warning: {e}")

        # 1. Fetch Data (Parallel-ish)
        # We need Current Price (Quote) + Sentiment + History (Candles)
        quote_task = asyncio.to_thread(finnhub_client.quote, ticker) if finnhub_client else None
        sentiment_task = asyncio.to_thread(fetch_sentiment, ticker)
        history_task = fetch_historical_data(ticker)
        
        # Execute
        quote_res = await quote_task if quote_task else None
        sentiment_score = await sentiment_task
        df = await history_task
        
        current_price = 0.0
        
        # 2. Process Quote (The Baseline)
        if quote_res and 'c' in quote_res:
             current_price = float(quote_res['c'])
             current_prices[ticker] = current_price # Store for valuation
             
             sent_str = f"| Sentiment: {sentiment_score:.2f}" if sentiment_score is not None else "| No Sentiment"
             print(f"   📊 Price: {current_price} {sent_str}")
             
             # Log Telemetry (Everything required for Dashboard)
             log_watchlist_data(bq_client, table_id, ticker, current_price, sentiment_score)
        else:
             print(f"   ⚠️  Could not fetch quote for {ticker}. Skipping.")
             continue

        # 3. Process Strategy (The Bonus)
        if df is not None:
            # Calculate Indicators
            market_data = calculate_technical_indicators(df)
            
            if market_data:
                # Overwrite price with candle close if needed, but Quote is usually fresher.
                # We'll use the calculated SMAs.
                market_data['current_price'] = current_price
                market_data['sentiment_score'] = sentiment_score
                
                # Fetch Portfolio State for Stop Loss
                try:
                    p_state = portfolio_manager.get_state(ticker)
                    market_data['avg_price'] = p_state.get('avg_price', 0.0)
                    market_data['holdings'] = p_state.get('holdings', 0.0) # For logic awareness
                except:
                    market_data['avg_price'] = 0.0

                print(f"      SMAs: SMA20={market_data['sma_20']:.2f} | SMA50={market_data['sma_50']:.2f}")

                # Evaluate Strategy
                signal = signal_agent.evaluate_strategy(market_data)
                
                status = "logged_no_signal"
                if signal:
                    print(f"   🚨 SIGNAL DETECTED: {signal['action']} {ticker}")
                    signal['ticker'] = ticker
                    exec_result = execution_manager.place_order(signal)
                    status = f"executed_{exec_result['status']}"
                    results.append({"ticker": ticker, "price": current_price, "signal": signal, "status": status})
                else:
                     results.append({"ticker": ticker, "price": current_price, "status": status})
            else:
                 print(f"      ⚠️  Insufficient history for indicators.")
        else:
             print(f"      ⚠️  No historical data (Strategy Skipped).")
             results.append({"ticker": ticker, "price": current_price, "status": "tracking_only"})

        await asyncio.sleep(1.1) # Rate limit friendly

        await asyncio.sleep(1.1) # Rate limit friendly
    
    # --- END OF CYCLE: PERFORMANCE LOGGING ---
    print("🏁 Cycle Complete. Calculating Total Equity...")
    try:
        from telemetry import log_performance
        performance_table = f"{PROJECT_ID}.trading_data.performance_logs"
        
        metrics = portfolio_manager.calculate_total_equity(current_prices)
        log_performance(bq_client, performance_table, metrics)
        
        # Append equity to results for API response
        results.append({"type": "performance_summary", "data": metrics})
        
    except Exception as e:
        print(f"❌ Performance Calculation Failed: {e}")

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
        error_msg = "❌ EXCHANGE_API_KEY is missing or invalid."
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 401

    try:
        data = await run_audit()

        if not data:
             return jsonify({
                "status": "warning",
                "message": "No data returned."
            }), 200

        return jsonify({
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": data
        }), 200
    except Exception as e:
        print(f"🔥 Critical Failure: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 5. LOCAL RUNNER ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
