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
from sentiment_analyzer import SentimentAnalyzer

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
table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"
portfolio_table_id = f"{PROJECT_ID}.trading_data.portfolio"

# Initialize AI Sentiment Analyzer
sentiment_analyzer = SentimentAnalyzer(PROJECT_ID)

# Initialize Trading Agents
# specific risk/vol settings can be loaded from env if needed
signal_agent = SignalAgent() 
portfolio_manager = PortfolioManager(bq_client, portfolio_table_id)
execution_manager = ExecutionManager(portfolio_manager)

# --- 2. CORE UTILITIES ---

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def _get_ny_time():
    return datetime.now(pytz.timezone('America/New_York'))

# Retrieve Alpaca Keys
ALPACA_KEY = os.environ.get('ALPACA_API_KEY')
ALPACA_SECRET = os.environ.get('ALPACA_API_SECRET')

async def fetch_historical_data(ticker):
    """Fetches daily candles for the last 60 days using Alpaca."""
    loop = asyncio.get_event_loop()
    
    def get_candles():
        if not ALPACA_KEY or not ALPACA_SECRET:
            print(f"⚠️  Alpaca keys missing for {ticker}")
            return None

        try:
            client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
            
            # Alpaca expects datetime objects
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=90) # Buffer for 60 trading days
            
            request_params = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed="iex" 
            )
            
            bars = client.get_stock_bars(request_params)
            
            if not bars.data:
                print(f"⚠️  Alpaca returned no data for {ticker}")
                return None
            
            # Convert to DataFrame
            # Alpaca returns a dict with 'symbol' as key, list of bars as value if single symbol?
            # actually bars.df works great
            df = bars.df.reset_index()
            
            # Filter for specific ticker just in case
            df = df[df['symbol'] == ticker]
            
            if df.empty:
                 return None

            # Normalize column names
            # Alpaca: timestamp, open, high, low, close, volume, trade_count, vwap
            # Internal: t, o, h, l, c, v
            df_norm = pd.DataFrame({
                't': df['timestamp'],
                'o': df['open'],
                'h': df['high'],
                'l': df['low'],
                'c': df['close'],
                'v': df['volume']
            })
            
            return df_norm
            
        except Exception as e:
            print(f"❌ Alpaca Error for {ticker}: {e}")
            return None

    return await loop.run_in_executor(None, get_candles)

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
    """
    Fetches news sentiment using Gemini 1.5 AI Analysis of real headlines.
    Fallbacks to Finnhub's pre-calculated score if AI fails.
    """
    if not finnhub_client: 
        return None
        
    try:
        # 1. Try AI Analysis of Company News
        sentiment_score = None
        
        # Get news from last 24 hours
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        _from = start_date.strftime('%Y-%m-%d')
        _to = end_date.strftime('%Y-%m-%d')
        
        # Fetch headlines
        news = finnhub_client.company_news(ticker, _from=_from, _to=_to)
        
        if news:
            print(f"📰 Found {len(news)} news items for {ticker}. Asking Gemini...")
            sentiment_score = sentiment_analyzer.analyze_news(ticker, news)
        
        # If Gemini returned a score (non-zero or even zero if explicitly neutral), usage it.
        # But if analyze_news returns 0.0 it's ambiguous (neutral or failure).
        # Let's assume if it returns non-zero it's a valid signal.
        if sentiment_score is not None and sentiment_score != 0.0:
            return sentiment_score

        # 2. Fallback to Finnhub's Generic Score
        print(f"⚠️  No strong AI signal for {ticker}. Falling back to Finnhub Sentiment.")
        res = finnhub_client.news_sentiment(ticker)
        
        if res and 'sentiment' in res:
             bullish = res['sentiment'].get('bullishPercent', 0.5)
             bearish = res['sentiment'].get('bearishPercent', 0.5)
             return bullish - bearish
             
        return 0.0 # Neutral default
        
    except Exception as e:
        print(f"⚠️  Sentiment fetch failed for {ticker}: {e}")
        return 0.0

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

            # 2.5 Log to BigQuery (Watchlist)
            # Ensures data is captured even if technical analysis fails (e.g. 403 error)
            log_watchlist_data(bq_client, table_id, ticker, current_price, sentiment_score)

            # 3. Calculate Technical Indicators
            indicators = calculate_technical_indicators(df)

            if indicators:
                # 4. Generate Signal
                # Prepare market data for the agent
                market_data = {
                    "current_price": current_price,
                    "sma_20": indicators['sma_20'],
                    "sma_50": indicators['sma_50'],
                    "bb_upper": indicators['bb_upper'],
                    "bb_lower": indicators['bb_lower'],
                    "sentiment_score": sentiment_score,
                    # We need avg_price for Stop Loss, fetch it from portfolio
                    # For now, we'll try to get it if possible, or default to 0
                    "avg_price": 0.0 
                }
                
                # Fetch Portfolio State for Stop Loss context
                try: 
                    # We should probably have fetched this earlier or cached it
                    # But for now, let's keep it simple or skip it if too complex to fetch here synchronous
                    # state = portfolio_manager.get_state(ticker)
                    # market_data['avg_price'] = state.get('avg_price', 0.0)
                    pass 
                except:
                    pass

                signal_dict = signal_agent.evaluate_strategy(market_data)
                
                # Unwrap the signal
                # SignalAgent returns: {"action": "BUY/SELL", "price": ..., "reason": ...} or None
                action = signal_dict['action'] if signal_dict else "HOLD"
                signal_reason = signal_dict['reason'] if signal_dict else None
                
                print(f"   📊 {ticker}: Signal: {action} (Reason: {signal_reason})")

                # F. Execute Trade (if valid)
                if action in ["BUY", "SELL"]:
                    # For BUY, we need to know how much cash to use
                    # We re-fetch global cash in case a previous iteration used it
                    current_global_cash = portfolio_manager.get_cash_balance()
                    
                    # Allocation Logic:
                    # Simple rule: Use up to $10k or available cash, whichever is lower
                    trade_size_limit = 10000.0 
                    allocation = min(current_global_cash, trade_size_limit)
                    
                    exec_result = execution_manager.place_order(
                        ticker=ticker, 
                        action=action, 
                        quantity=0, # Manager calculates quantity based on price/cash
                        price=current_price,
                        cash_available=allocation 
                    )
                    
                    status = f"executed_{exec_result.get('status', 'UNKNOWN')}"
                    results.append({"ticker": ticker, "price": current_price, "signal": action, "status": status, "details": exec_result})
                else:
                    print(f"   ⏳ {ticker}: No Action ({action})")
                    results.append({"ticker": ticker, "price": current_price, "signal": "HOLD", "status": "tracking_only"})
            else:
                print(f"      ⚠️  Insufficient history for indicators.")
                results.append({"ticker": ticker, "price": current_price, "status": "tracking_only"})
        else:
            print(f"      ⚠️  No historical data (Strategy Skipped).")
            results.append({"ticker": ticker, "price": current_price, "status": "tracking_only"})

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
