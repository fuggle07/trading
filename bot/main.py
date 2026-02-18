import os
import asyncio
import finnhub
import pandas as pd
from flask import Flask, jsonify
from datetime import datetime, timezone, timedelta
from telemetry import log_watchlist_data, log_decision
import pytz
from google.cloud import bigquery
from signal_agent import SignalAgent
from execution_manager import ExecutionManager
from portfolio_manager import PortfolioManager
from sentiment_analyzer import SentimentAnalyzer
from fundamental_agent import FundamentalAgent
from ticker_ranker import TickerRanker

# --- 1. INITIALIZATION ---
app = Flask(__name__)
app.url_map.strict_slashes = False

# Retrieve the key
FINNHUB_KEY = os.environ.get("EXCHANGE_API_KEY")

def check_api_key():
    """Validates that the API key is present."""
    if not FINNHUB_KEY or len(FINNHUB_KEY) < 10:
        return False
    return True

# Initialize Clients
finnhub_client = finnhub.Client(api_key=FINNHUB_KEY) if FINNHUB_KEY else None

# Initialize BigQuery Client
PROJECT_ID = os.environ.get("PROJECT_ID", "trading-12345")
bq_client = bigquery.Client(project=PROJECT_ID)
table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"
portfolio_table_id = f"{PROJECT_ID}.trading_data.portfolio"

# Initialize AI Sentiment Analyzer
sentiment_analyzer = SentimentAnalyzer(PROJECT_ID)

# Initialize Trading Agents
# Load Mortgage Rate and calculate Tax-Adjusted Hurdle
# Assuming 35% tax deductibility as per user request
raw_mortgage_rate = float(os.environ.get("MORTGAGE_RATE", 0.0))
tax_adjusted_hurdle = raw_mortgage_rate * (1 - 0.35)

print(f"🏦 Mortgage Rate: {raw_mortgage_rate:.2%}")
print(f"📉 Tax-Adjusted Hurdle: {tax_adjusted_hurdle:.2%}")

# Handle Volatility Sensitivity
base_vol_threshold = 0.25
vol_sensitivity = float(os.environ.get("VOLATILITY_SENSITIVITY", 1.0))
final_vol_threshold = base_vol_threshold * vol_sensitivity

print(f"🌊 Volatility Sensitivity: {vol_sensitivity:.1f}")
print(f"🛡️  Final Volatility Threshold: {final_vol_threshold:.1%}")

signal_agent = SignalAgent(
    hurdle_rate=tax_adjusted_hurdle, vol_threshold=final_vol_threshold
)
portfolio_manager = PortfolioManager(bq_client, portfolio_table_id)
execution_manager = ExecutionManager(portfolio_manager)
fundamental_agent = FundamentalAgent(finnhub_client=finnhub_client)
ticker_ranker = TickerRanker(PROJECT_ID, bq_client)

# --- 2. CORE UTILITIES ---

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def _get_ny_time():
    return datetime.now(pytz.timezone("America/New_York"))

# Retrieve Alpaca Keys
ALPACA_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET")

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
            start = end - timedelta(days=90)  # Buffer for 60 trading days

            request_params = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed="iex",
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
            df = df[df["symbol"] == ticker]

            if df.empty:
                return None

            # Normalize column names
            # Alpaca: timestamp, open, high, low, close, volume, trade_count, vwap
            # Internal: t, o, h, l, c, v
            df_norm = pd.DataFrame(
                {
                    "t": df["timestamp"],
                    "o": df["open"],
                    "h": df["high"],
                    "l": df["low"],
                    "c": df["close"],
                    "v": df["volume"],
                }
            )

            return df_norm

        except Exception as e:
            print(f"❌ Alpaca Error for {ticker}: {e}")
            return None

    import asyncio
    try:
        return await asyncio.wait_for(loop.run_in_executor(None, get_candles), timeout=20)
    except asyncio.TimeoutError:
        print(f"⏳ Alpaca Timeout for {ticker}")
        return None

def calculate_technical_indicators(df):
    """Calculates SMA-20, SMA-50, and Bollinger Bands."""
    if df is None or len(df) < 50:
        return None

    # Calculate SMAs
    df["sma_20"] = df["c"].rolling(window=20).mean()
    df["sma_50"] = df["c"].rolling(window=50).mean()

    # Calculate Bollinger Bands (20-day, 2 std dev)
    rolling_std = df["c"].rolling(window=20).std()
    df["bb_upper"] = df["sma_20"] + (rolling_std * 2)
    df["bb_lower"] = df["sma_20"] - (rolling_std * 2)

    # Return the latest slice as a dictionary for the strategy
    latest = df.iloc[-1]

    # Ensure no NaN values in the latest slice (can happen if data is too short)
    if pd.isna(latest["sma_50"]):
        return None

    return {
        "current_price": latest["c"],
        "sma_20": latest["sma_20"],
        "sma_50": latest["sma_50"],
        "bb_upper": latest["bb_upper"],
        "bb_lower": latest["bb_lower"],
        "timestamp": latest["t"],
    }

# --- 3. THE AUDIT ENGINE ---

async def fetch_sentiment(ticker):
    """
    Hybrid Sentiment Engine:
    1. Vertex AI (Gemini) Deep Analysis of headlines
    2. Finnhub fallback for basic scores
    """
    try:
        sentiment_score = None

        # Get news from last 24 hours
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        _from = start_date.strftime("%Y-%m-%d")
        _to = end_date.strftime("%Y-%m-%d")

        # Fetch headlines (Sync call -> Thread)
        news = await asyncio.to_thread(finnhub_client.company_news, ticker, _from=_from, to=_to)

        if news:
            print(f"📰 Found {len(news)} news items for {ticker}. Asking Gemini...")
            sentiment_score = await sentiment_analyzer.analyze_news(ticker, news)

        # If Gemini returned a score (non-zero), use it.
        if sentiment_score is not None and sentiment_score != 0.0:
            return sentiment_score

        # 2. Fallback to Finnhub's Generic Score
        print(f"⚠️  No strong AI signal for {ticker}. Falling back to Finnhub Sentiment.")
        try:
            res = await asyncio.to_thread(finnhub_client.news_sentiment, ticker)
            if res and "sentiment" in res:
                bullish = res["sentiment"].get("bullishPercent", 0.5)
                bearish = res["sentiment"].get("bearishPercent", 0.5)
                return bullish - bearish
        except Exception as e:
            if "403" in str(e):
                print(f"ℹ️  Finnhub Sentiment fallback skipped (Premium only) for {ticker}")
            else:
                print(f"⚠️  Finnhub Sentiment fallback failed for {ticker}: {e}")

        return 0.0  # Neutral default
    except Exception as e:
        print(f"⚠️  Global fetch_sentiment error for {ticker}: {e}")
        return 0.0

# --- 3. THE AUDIT ENGINE ---

async def run_audit():
    """
    Refactored Audit Pipeline:
    Phase 1: Intelligence Gathering (Parallel Data Fetch)
    Phase 2: Portfolio Analysis & Conviction Swapping
    Phase 3: Execution (SELLs first, then BUYs)
    """
    tickers_env = os.environ.get("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD")
    tickers = [t.strip() for t in tickers_env.split(",") if t.strip()]
    print(f"🔍 Starting Multi-Phase Audit for: {tickers}")

    # --- Phase 1: Intelligence Gathering ---
    ticker_intel = {}
    current_prices = {}

    for ticker in tickers:
        print(f"   📡 Gathering Intel for {ticker}...")
        try:
            # Parallel fetch for a single ticker to save time
            quote_task = asyncio.to_thread(finnhub_client.quote, ticker) if finnhub_client else None
            sentiment_task = fetch_sentiment(ticker)
            fundamental_task = fundamental_agent.evaluate_health(ticker)
            deep_health_task = fundamental_agent.evaluate_deep_health(ticker)
            history_task = fetch_historical_data(ticker)
            confidence_task = get_latest_confidence(ticker)

            # Execute gather with error handling
            intel_results = await asyncio.gather(
                quote_task, sentiment_task, fundamental_task, deep_health_task, history_task, confidence_task,
                return_exceptions=True
            )

            # Unpack safely
            quote_res = intel_results[0] if not isinstance(intel_results[0], Exception) else None
            sentiment_score = intel_results[1] if not isinstance(intel_results[1], Exception) else 0.0
            health = intel_results[2] if not isinstance(intel_results[2], Exception) else (False, "Health fetch failed")
            deep_health = intel_results[3] if not isinstance(intel_results[3], Exception) else (False, "Deep health fetch failed")
            df = intel_results[4] if not isinstance(intel_results[4], Exception) else None
            confidence = intel_results[5] if not isinstance(intel_results[5], Exception) else 0

            if quote_res and isinstance(quote_res, dict) and "c" in quote_res:
                price = float(quote_res["c"])
                current_prices[ticker] = price
                indicators = calculate_technical_indicators(df)

                ticker_intel[ticker] = {
                    "price": price,
                    "sentiment": float(sentiment_score or 0.0),
                    "is_healthy": bool(health[0]),
                    "health_reason": str(health[1]),
                    "is_deep_healthy": bool(deep_health[0]),
                    "deep_health_reason": str(deep_health[1]),
                    "confidence": int(confidence or 0),
                    "indicators": indicators
                }
                # Log to Watchlist (Persistence)
                log_watchlist_data(bq_client, table_id, ticker, price, sentiment_score)
        except Exception as e:
            print(f"      ⚠️ Failed to gather intel for {ticker}: {e}")

        await asyncio.sleep(0.5) # Rate limit spread

    # --- Phase 2: Portfolio Analysis & Conviction Swapping ---
    print("   ⚖️ Analyzing Portfolio Relative Strength...")
    val_data = portfolio_manager.calculate_total_equity(current_prices)
    total_equity = val_data.get("total_equity", 0.0)

    # Identify Held vs Non-Held for Swapping
    held_tickers = {item["ticker"]: item for item in val_data.get("breakdown", []) if item.get("market_value", 0) > 0}
    non_held_tickers = [t for t in ticker_intel if t not in held_tickers]

    # Generate Initial Signals
    signals = {}
    for ticker, intel in ticker_intel.items():
        indicators = intel.get("indicators")
        if indicators:
            total_market_val = val_data.get("total_market_value", 0.0)
            exposure = total_market_val / total_equity if total_equity > 0 else 0.0

            market_data = {
                "ticker": ticker,
                "current_price": intel["price"],
                "sma_20": indicators["sma_20"],
                "sma_50": indicators["sma_50"],
                "bb_upper": indicators["bb_upper"],
                "bb_lower": indicators["bb_lower"],
                "sentiment_score": intel["sentiment"],
                "is_healthy": intel["is_healthy"],
                "health_reason": intel["health_reason"],
                "is_deep_healthy": intel["is_deep_healthy"],
                "deep_health_reason": intel["deep_health_reason"],
                "avg_price": held_tickers.get(ticker, {}).get("avg_price", 0.0),
                "prediction_confidence": intel["confidence"],
                "is_low_exposure": exposure < 0.25
            }

            sig = signal_agent.evaluate_strategy(market_data, force_eval=True)
            if sig:
                signals[ticker] = sig

    # REBALANCING LOGIC: The Conviction Swap
    weakest_link = None
    for t in held_tickers:
        intel = ticker_intel.get(t)
        if intel:
            conf = intel.get("confidence", 0)
            if conf < 50:
                if weakest_link is None or conf < ticker_intel[weakest_link].get("confidence", 0):
                    weakest_link = t

    rising_star = None
    for t in non_held_tickers:
        intel = ticker_intel.get(t)
        if intel:
            conf = intel.get("confidence", 0)
            if conf > 80:
                 if rising_star is None or conf > ticker_intel[rising_star].get("confidence", 0):
                     rising_star = t

    if weakest_link and rising_star:
        weakest_conf = ticker_intel[weakest_link].get("confidence", 0)
        star_conf = ticker_intel[rising_star].get("confidence", 0)

        log_decision(rising_star, "SWAP", f"Rotating out of {weakest_link} ({weakest_conf}%) into {rising_star} ({star_conf}%)")
        signals[weakest_link] = {"action": "SELL", "reason": "CONVICTION_SWAP", "price": ticker_intel[weakest_link]["price"]}
        if rising_star not in signals:
            signals[rising_star] = {"action": "BUY", "reason": "CONVICTION_ROTATION", "price": ticker_intel[rising_star]["price"]}

    # --- Phase 3: Coordinated Execution ---
    print("   🚀 Executing Coordinated Trades...")
    execution_results = []

    trading_enabled = os.environ.get("TRADING_ENABLED", "true").lower() == "true"
    is_market_open = signal_agent.is_market_open()
    effective_enabled = trading_enabled and is_market_open

    # 1. Execute SELLs First
    for ticker, sig in signals.items():
        if sig.get("action") == "SELL":
            reason = sig.get("reason", "Strategy Signal")
            if not effective_enabled:
                log_decision(ticker, "SKIP", f"DRY_RUN: Intent SELL ({reason})")
                status = "dry_run_sell"
            else:
                exec_res = execution_manager.place_order(ticker, "SELL", 0, sig["price"], reason=reason)
                status = f"executed_{exec_res.get('status', 'FAIL')}"
                log_decision(ticker, "SELL", f"Execution Status: {status} | Reason: {reason}")

            execution_results.append({"ticker": ticker, "signal": "SELL", "status": status, "reason": reason})

    # 2. Execute BUYs
    for ticker, sig in signals.items():
        if sig.get("action") == "BUY":
            reason = sig.get("reason", "Strategy Signal")
            if not effective_enabled:
                log_decision(ticker, "SKIP", f"DRY_RUN: Intent BUY ({reason})")
                status = "dry_run_buy"
            else:
                cash_pool = portfolio_manager.get_cash_balance()
                room_to_buy = total_equity * 0.25 - held_tickers.get(ticker, {}).get("market_value", 0.0)

                base_unit = total_equity * 0.05
                intel = ticker_intel.get(ticker, {})
                sentiment = float(intel.get("sentiment", 0.0))
                multiplier = 1.0 + max(0.0, sentiment)
                allocation = min(base_unit * multiplier, room_to_buy, cash_pool)

                if allocation > 100:
                    exec_res = execution_manager.place_order(ticker, "BUY", 0, sig["price"], cash_available=allocation, reason=reason)
                    status = f"executed_{exec_res.get('status', 'FAIL')}"
                    log_decision(ticker, "BUY", f"Execution Status: {status} | Alloc: ${allocation:.2f} | Reason: {reason}")
                else:
                    log_decision(ticker, "SKIP", f"Insufficient Allocation (${allocation:.2f} < $100) or Room to Buy.")
                    status = "skipped_insufficient_funds"

            execution_results.append({"ticker": ticker, "signal": "BUY", "status": status, "reason": reason})

    # Performance Logging
    try:
        from telemetry import log_performance
        final_conv_prices = {t: intel["price"] for t, intel in ticker_intel.items()}
        perf_metrics = portfolio_manager.calculate_total_equity(final_conv_prices)
        log_performance(bq_client, f"{PROJECT_ID}.trading_data.performance_logs", perf_metrics)
        execution_results.append({"type": "performance_summary", "data": perf_metrics})
    except Exception as e:
        print(f"      ❌ Perf Log Fail: {e}")

    return execution_results

from typing import List, Dict, Optional

async def get_latest_confidence(ticker: str) -> Optional[int]:
    """Fetches the latest prediction confidence for a ticker from BQ."""
    query = f"""
        SELECT confidence
        FROM `{PROJECT_ID}.trading_data.ticker_rankings`
        WHERE ticker = '{ticker}'
        AND DATE(timestamp) = CURRENT_DATE('America/New_York')
        ORDER BY timestamp DESC
        LIMIT 1
    """
    try:
        loop = asyncio.get_event_loop()
        query_job = await loop.run_in_executor(None, bq_client.query, query)
        results = await loop.run_in_executor(None, query_job.to_dataframe)
        if not results.empty:
            return int(results.iloc[0]["confidence"])
    except Exception as e:
        print(f"⚠️ Error fetching confidence for {ticker}: {e}")
    return None

@app.route("/rank-tickers", methods=["POST"])
async def run_ranker_endpoint():
    """Trigger the morning ticker ranking job."""
    tickers = os.environ.get("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD").split(",")
    try:
        results = await ticker_ranker.rank_and_log(tickers)
        return jsonify({"status": "success", "results": results}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 4. FLASK ROUTES ---

@app.route("/health")
def health():
    return (
        jsonify(
            {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
        ),
        200,
    )

@app.route("/run-audit", methods=["POST"])
async def run_audit_endpoint():
    # 1. Immediate Key Validation
    if not check_api_key():
        error_msg = "❌ EXCHANGE_API_KEY is missing or invalid."
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 401

    try:
        data = await run_audit()

        if not data:
            return jsonify({"status": "warning", "message": "No data returned."}), 200

        return (
            jsonify(
                {
                    "status": "complete",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "results": data,
                }
            ),
            200,
        )
    except Exception as e:
        print(f"🔥 Critical Failure: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 5. LOCAL RUNNER ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
