import os
import asyncio
import finnhub
import pandas as pd
from flask import Flask, jsonify
from datetime import datetime, timezone, timedelta
from bot.telemetry import log_watchlist_data, log_macro_snapshot, log_decision
import pytz
import traceback
from google.cloud import bigquery
from bot.signal_agent import SignalAgent
from bot.execution_manager import ExecutionManager
from bot.portfolio_manager import PortfolioManager
from bot.sentiment_analyzer import SentimentAnalyzer
from bot.fundamental_agent import FundamentalAgent
from bot.ticker_ranker import TickerRanker
from bot.feedback_agent import FeedbackAgent
from bot.portfolio_reconciler import PortfolioReconciler

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
# Actual Project ID: utopian-calling-429014-r9
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")
bq_client = bigquery.Client(project=PROJECT_ID)
table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"
portfolio_table_id = f"{PROJECT_ID}.trading_data.portfolio"

# Finnhub Client (Now checking EXCHANGE_API_KEY)
FINNHUB_KEY = os.environ.get("EXCHANGE_API_KEY") or os.environ.get("FINNHUB_KEY")
finnhub_client = finnhub.Client(api_key=FINNHUB_KEY) if FINNHUB_KEY else None

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
feedback_agent = FeedbackAgent(PROJECT_ID, bq_client)
reconciler = PortfolioReconciler(PROJECT_ID, bq_client)

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
                print(f"⚠️  Alpaca data frame empty for {ticker}")
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

            print(f"[{ticker}] 📊 Alpaca Data Fetched: {len(df)} rows")
            return df_norm

        except Exception as e:
            print(f"❌ Alpaca Error for {ticker}: {e}")
            return None

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, get_candles), timeout=20
        )
    except asyncio.TimeoutError:
        print(f"⏳ Alpaca Timeout for {ticker}")
        return None


async def get_macro_context() -> dict:
    """
    Fetches $SPY, $QQQ, VIX, and Treasury Rates to provide holistic macro context.
    Returns a dict for AI consumption and a formatted string for logging.
    """
    macro_data = {
        "indices": {},
        "rates": {},
        "vix": 0.0,
        "formatted": "Market Context: Stable"
    }
    
    try:
        # Fetch data in parallel
        indices_task = fundamental_agent.get_market_indices()
        rates_task = fundamental_agent.get_treasury_rates()
        calendar_task = fundamental_agent.get_economic_calendar()
        
        indices, rates, calendar = await asyncio.gather(indices_task, rates_task, calendar_task)
        
        macro_data["indices"] = indices
        macro_data["rates"] = rates
        macro_data["calendar"] = calendar
        macro_data["vix"] = indices.get("vix", 0.0)
        
        parts = []
        if "spy_perf" in indices:
            parts.append(f"SPY: {indices['spy_perf']:.2f}%")
        if "qqq_perf" in indices:
            parts.append(f"QQQ: {indices['qqq_perf']:.2f}%")
        if "10Y" in rates:
            parts.append(f"10Y Yield: {rates['10Y']:.2f}%")
        if macro_data["vix"] > 0:
            parts.append(f"VIX: {macro_data['vix']:.2f}")
            
        if parts:
            macro_data["formatted"] = f"Market Context: {', '.join(parts)}"
            
    except Exception as e:
        logger.error(f"⚠️ Failed to fetch macro context: {e}")
    
    return macro_data


def calculate_technical_indicators(df, ticker="Unknown"):
    """Calculates SMA-20, SMA-50, and Bollinger Bands."""
    if df is None:
        return None
    
    if len(df) < 50:
        print(
            f"⚠️  [{ticker}] Insufficient technical data: {len(df)} rows < 50 required"
        )
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


async def fetch_sentiment(ticker, lessons="", context=None):
    """
    Hybrid Sentiment Engine:
    1. Vertex AI (Gemini) Deep Analysis of headlines + context
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
        news = await asyncio.to_thread(
            finnhub_client.company_news, ticker, _from=_from, to=_to
        )

        if news:
            print(
                f"[{ticker}] 📰 Found {len(news)} news items for {ticker}. Asking Gemini..."
            )
            result = await sentiment_analyzer.analyze_news(ticker, news, lessons, context=context)
            sentiment_score, gemini_reasoning = result if isinstance(result, tuple) else (result, "")
        else:
            gemini_reasoning = ""

        # If Gemini returned a score (non-zero), use it.
        if sentiment_score is not None and sentiment_score != 0.0:
            return sentiment_score, gemini_reasoning

        # 2. Fallback to Finnhub's Generic Score
        print(
            f"[{ticker}] ⚠️  No strong AI signal for {ticker}. Falling back to Finnhub Sentiment."
        )
        try:
            res = await asyncio.to_thread(finnhub_client.news_sentiment, ticker)
            if res and "sentiment" in res:
                bullish = res["sentiment"].get("bullishPercent", 0.5)
                bearish = res["sentiment"].get("bearishPercent", 0.5)
                return bullish - bearish
        except Exception as e:
            if "403" in str(e):
                print(
                    f"[{ticker}] ℹ️  Finnhub Sentiment fallback skipped (Premium only) for {ticker}"
                )
            else:
                print(
                    f"[{ticker}] ⚠️  Finnhub Sentiment fallback failed for {ticker}: {e}"
                )

        return 0.0, ""  # Neutral default
    except Exception as e:
        print(f"[{ticker}] ⚠️  Global fetch_sentiment error for {ticker}: {e}")
        return 0.0, ""


# --- 3. THE AUDIT ENGINE ---


async def run_audit():
    """
    Refactored Audit Pipeline:
    Phase 1: Intelligence Gathering (Parallel Data Fetch)
    Phase 2: Portfolio Analysis & Conviction Swapping
    Phase 3: Execution (SELLs first, then BUYs)
    """
    tickers_env = os.environ.get("BASE_TICKERS", "NVDA,AAPL,MU,MSFT,AMD")
    base_tickers = [t.strip() for t in tickers_env.split(",") if t.strip()]
    
    # --- Phase 1: Portfolio Awareness & Intel Gathering ---
    print("🔄 Fetching Portfolio & Intel...")
    held_tickers = portfolio_manager.get_held_tickers()
    
    # Audit all monitored tickers PLUS anything we currently hold (safety first)
    tickers = list(set(base_tickers + list(held_tickers.keys())))
    print(f"🔍 Starting Multi-Phase Audit for: {tickers}")

    # --- Phase 0: Reconciliation ---
    print("🔄 Reconciling Portfolio with Alpaca...")
    try:
        await asyncio.to_thread(reconciler.sync_portfolio)
        await asyncio.to_thread(reconciler.sync_executions)
    except Exception as e:
        print(f"⚠️ Reconciliation Warning: {e}")

    # already fetched held_tickers above
    ticker_intel = {}
    current_prices = {}

    # 1. Fetch Hard-Learned Lessons (Intraday Feedback Loop)
    # 2. Fetch Enriched Macro Context
    lessons_task = feedback_agent.get_recent_lessons(limit=3)
    macro_task = get_macro_context()
    
    lessons, macro_data = await asyncio.gather(lessons_task, macro_task)
    macro_context_str = macro_data.get("formatted", "Market Context: Stable")
    
    if lessons:
        print("🧠 Injecting Hard-Learned Lessons into Intraday Analysis...")
    print(f"🌍 {macro_context_str}")

    # Store macro snapshot to BigQuery for historical analysis
    try:
        log_macro_snapshot(bq_client, PROJECT_ID, macro_data)
    except Exception as e:
        print(f"⚠️ Macro snapshot log failed: {e}")

    for ticker in tickers:
        print(f"[{ticker}] 📡 Gathering Intel for {ticker}...")
        try:
            # Parallel fetch for a single ticker to save time
            quote_task = asyncio.to_thread(finnhub_client.quote, ticker) if finnhub_client else None
            intelligence_task = fundamental_agent.get_intelligence_metrics(ticker)
            fundamental_task = fundamental_agent.evaluate_health(ticker)
            deep_health_task = fundamental_agent.evaluate_deep_health(ticker)
            history_task = fetch_historical_data(ticker)
            confidence_task = get_latest_confidence(ticker)
            
            # FMP Technical Indicators
            sma20_task = fundamental_agent.get_technical_indicator(ticker, "sma", period=20)
            sma50_task = fundamental_agent.get_technical_indicator(ticker, "sma", period=50)
            rsi_task = fundamental_agent.get_technical_indicator(ticker, "rsi", period=14)
            std_task = fundamental_agent.get_technical_indicator(ticker, "standarddeviation", period=20)

            # Execute gather with error handling
            intel_results = await asyncio.gather(
                quote_task, intelligence_task, fundamental_task, deep_health_task,
                history_task, confidence_task, sma20_task, sma50_task, rsi_task, std_task,
                return_exceptions=True,
            )

            # --- UNPACK ALL RESULTS ---
            res_quote = intel_results[0] if not isinstance(intel_results[0], Exception) else None
            res_intel = intel_results[1] if not isinstance(intel_results[1], Exception) else {}
            res_health = intel_results[2] if not isinstance(intel_results[2], Exception) else (False, "Health fail")
            res_deep = intel_results[3] if not isinstance(intel_results[3], Exception) else (False, "Deep fail", 0)
            res_history = intel_results[4] if not isinstance(intel_results[4], Exception) else None
            res_conf = intel_results[5] if not isinstance(intel_results[5], Exception) else 0
            res_sma20 = intel_results[6] if not isinstance(intel_results[6], Exception) else None
            res_sma50 = intel_results[7] if not isinstance(intel_results[7], Exception) else None
            res_rsi = intel_results[8] if not isinstance(intel_results[8], Exception) else None
            res_std = intel_results[9] if not isinstance(intel_results[9], Exception) else None

            if res_quote and isinstance(res_quote, dict) and "c" in res_quote:
                price = float(res_quote["c"])
                current_prices[ticker] = price

                # --- PREPARE ENRICHED CONTEXT FOR AI ---
                sma20_val = float(res_sma20.get("sma", 0)) if res_sma20 else 0
                sma_stretch = ((price / sma20_val) - 1) * 100 if sma20_val > 0 else 0
                
                ai_context = {
                    "macro": macro_data, # Detailed macro dict for Gemini
                    "analyst_consensus": res_intel.get("analyst_consensus", "Neutral"),
                    "institutional_flow": res_intel.get("institutional_momentum", "Neutral"),
                    "rsi": float(res_rsi.get("rsi", 50)) if res_rsi else 50.0,
                    "sma_stretch_pct": round(sma_stretch, 2),
                }
                
                # Fetch sentiment with the enriched context
                sentiment_result = await fetch_sentiment(ticker, lessons, context=ai_context)
                sentiment_score, gemini_reasoning = sentiment_result if isinstance(sentiment_result, tuple) else (sentiment_result, "")

                # Process technicals
                indicators = calculate_technical_indicators(res_history, ticker)
                if indicators:
                    if res_sma20: indicators["sma_20"] = float(res_sma20.get("sma", indicators["sma_20"]))
                    if res_sma50: indicators["sma_50"] = float(res_sma50.get("sma", indicators["sma_50"]))
                    if res_sma20 and res_std:
                        sma = float(res_sma20.get("sma", indicators["sma_20"]))
                        std = float(res_std.get("standardDeviation", 0))
                        indicators["bb_upper"] = sma + (std * 2)
                        indicators["bb_lower"] = sma - (std * 2)

                ticker_intel[ticker] = {
                    "price":            price,
                    "sentiment":        float(sentiment_score or 0.0),
                    "gemini_reasoning": gemini_reasoning,
                    "rsi":              float(res_rsi.get("rsi", 50)) if res_rsi else 50.0,
                    "is_healthy":       bool(res_health[0]),
                    "health_reason":    str(res_health[1]),
                    "is_deep_healthy":  bool(res_deep[0]),
                    "deep_health_reason": str(res_deep[1]),
                    "f_score":          int(res_deep[2]) if len(res_deep) > 2 else 0,
                    "confidence":       int(res_conf or 0),
                    "indicators":       indicators,
                    "history_res":      res_history
                }
                # Log to Watchlist — include all technical fields
                ind = indicators or {}
                log_watchlist_data(
                    bq_client, table_id, ticker, price, sentiment_score, int(res_conf or 0),
                    rsi=float(res_rsi.get("rsi", 0)) if res_rsi else None,
                    sma_20=ind.get("sma_20"),
                    sma_50=ind.get("sma_50"),
                    bb_upper=ind.get("bb_upper"),
                    bb_lower=ind.get("bb_lower"),
                    f_score=int(res_deep[2]) if len(res_deep) > 2 else None,
                    conviction=int(res_conf or 0),
                    gemini_reasoning=gemini_reasoning,
                )
        except Exception as e:
            print(f"[{ticker}] ⚠️ Failed to gather intel for {ticker}: {e}")

        await asyncio.sleep(0.5)  # Rate limit spread

    # --- Phase 2: Portfolio Analysis & Conviction Swapping ---
    print("⚖️ Analyzing Portfolio Relative Strength...")
    val_data = portfolio_manager.calculate_total_equity(current_prices)
    total_equity = val_data.get("total_equity", 0.0)
    total_market_value = val_data.get("total_market_value", 0.0)
    exposure = total_market_value / total_equity if total_equity > 0 else 0.0

    # Identify Held vs Non-Held for Swapping
    held_tickers = {
        item["ticker"]: item
        for item in val_data.get("breakdown", [])
        if item.get("market_value", 0) > 0
    }
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
                "f_score": intel["f_score"],
                "rsi": intel.get("rsi", 50.0),
                "avg_price": held_tickers.get(ticker, {}).get("avg_price", 0.0),
                "prediction_confidence": intel["confidence"],
                "is_low_exposure": exposure < 0.60,
            }

            sig = signal_agent.evaluate_strategy(market_data, force_eval=True)
            if sig:
                signals[ticker] = sig
        else:
            # Identify why indicators are missing
            history_res = intel.get("history_res")
            if isinstance(history_res, Exception):
                reason_msg = f"Alpaca API Error: {type(history_res).__name__}"
            elif history_res is None:
                reason_msg = "Alpaca returned None (Check API Keys/Feed)"
            else:
                # If we get here and indicators is None, it's likely calculate_technical_indicators returned None
                rows = len(history_res) if history_res is not None else 0
                reason_msg = f"Insufficient history ({rows} rows)"

            log_decision(
                ticker,
                "SKIP",
                f"Missing Technical Data ({reason_msg})",
            )

    # REBALANCING LOGIC: The Conviction Swap
    # We find the weakest link in our portfolio and potentially swap it for a rising star
    
    weakest_link = None
    # 1. Identify Weakest Link (Lowest Confidence OR Failed Fundamentals)
    for t in held_tickers:
        intel = ticker_intel.get(t)
        if intel:
            conf = intel.get("confidence", 0)
            is_deep = intel.get("is_deep_healthy", True)
            
            # SWAP TRIGGER: If confidence is low OR Fundamentals are "Low Quality" (< 40)
            if conf < 50 or not is_deep:
                # Prioritize is_deep failures (Fundamental Failures) as the weakest link
                if weakest_link is None:
                    weakest_link = t
                else:
                    current_weakest_is_deep = ticker_intel[weakest_link].get("is_deep_healthy", True)
                    # If current weakest is fundamentally OK, but this one isn't, replace it
                    if current_weakest_is_deep and not is_deep:
                         weakest_link = t
                    # If both are fundamentally bad, use the one with lower confidence
                    elif not current_weakest_is_deep and not is_deep:
                        if conf < ticker_intel[weakest_link].get("confidence", 0):
                            weakest_link = t
                    # If both are fundamentally OK, use the one with lower confidence
                    elif conf < ticker_intel[weakest_link].get("confidence", 0):
                        weakest_link = t

    # 2. Identify Rising Star (Highest Confidence + Fundamentals)
    rising_star = None
    best_star_conf = 0
    
    for t in non_held_tickers:
        intel = ticker_intel.get(t)
        if not intel: continue
        
        conf = intel.get("confidence", 0)
        
        # Candidate Check: Must be high confidence
        if conf > 80:
             if rising_star is None or conf > best_star_conf:
                 rising_star = t
                 best_star_conf = conf

    # 3. Evaluate Swap
    if rising_star and weakest_link:
        weakest_conf = ticker_intel[weakest_link].get("confidence", 0)
        star_intel = ticker_intel[rising_star]
        
        should_swap = signal_agent.check_conviction_swap(
            weakest_link, 
            weakest_conf, 
            rising_star, 
            best_star_conf,
            potential_fundamentals={
                "is_deep_healthy": star_intel["is_deep_healthy"],
                "f_score": star_intel["f_score"]
            }
        )
        
        if should_swap:
            weakest_conf = ticker_intel[weakest_link].get("confidence", 0)
            log_decision(
                rising_star,
                "BUY", # Action for the rising star
                f"Rotating out of {weakest_link} ({weakest_conf}%) into {rising_star} ({best_star_conf}%)",
            )
            signals[weakest_link] = {
                "action": "SELL",
                "reason": "CONVICTION_SWAP",
                "price": ticker_intel[weakest_link]["price"],
            }
            if rising_star not in signals or signals[rising_star]["action"] != "BUY":
                signals[rising_star] = {
                    "action": "BUY",
                    "reason": "CONVICTION_ROTATION",
                    "price": ticker_intel[rising_star]["price"],
                }
    elif exposure < 0.60:
        # Deployment Logic: If we have cash, buy the best thing available
        # BUT: Respect volatility and hygiene checks
        existing_sig = signals.get(rising_star, {})
        existing_action = existing_sig.get("action", "IDLE")
        
        # Extract technical signal from meta if available
        meta = existing_sig.get("meta", {})
        tech_signal = meta.get("technical", "UNKNOWN")

        # Check if the signal explicitly forbids trading
        is_valid_candidate = True
        
        # Reject if:
        # 1. Action is explicitly SELL
        # 2. Technical signal is VOLATILE_IGNORE
        # 3. Action is IDLE (meaning no buy signal was generated normally)
        if existing_action == "SELL" or tech_signal == "VOLATILE_IGNORE":
                is_valid_candidate = False
        
        # We also generally shouldn't override IDLE unless we are VERY sure, 
        # but 'Initial Deployment' is meant to be aggressive. 
        # However, if it was IDLE because of volatility, tech_signal would catch it.
            
        if is_valid_candidate and (rising_star not in signals or signals[rising_star]["action"] != "BUY"):
                # Check for volatility
                if tech_signal == "VOLATILE_IGNORE":
                    print(f"⚠️ Initial Deployment: Skipping {rising_star} due to high volatility despite high conviction.")
                elif existing_action == "SELL":
                    print(f"⚠️ Initial Deployment: Skipping {rising_star} due to SELL signal.")
                else: 
                    log_decision(
                        rising_star,
                        "BUY",
                        f"Initial Deployment: High Conviction Rising Star ({best_star_conf}%)",
                    )
                    signals[rising_star] = {
                        "action": "BUY",
                        "reason": "INITIAL_DEPLOYMENT",
                        "price": ticker_intel[rising_star]["price"],
                    }

    # Fallback Deployment: If we still have low exposure and no valid rising star was bought
    # Find the *next best* available candidate (conf > 60) that isn't volatile/sell
    if exposure < 0.60 and not any(s.get("reason") == "INITIAL_DEPLOYMENT" for s in signals.values()):
        best_deploy_candidate = None
        best_deploy_conf = 0

        for t in non_held_tickers:
            intel = ticker_intel.get(t)
            if not intel: continue
            
            conf = intel.get("confidence", 0)
            sig = signals.get(t, {})
            action = sig.get("action", "IDLE")
            tech_sig = sig.get("meta", {}).get("technical", "UNKNOWN")

            # Must be > 60 conf, not volatile, not sell
            if conf > 60 and action != "SELL" and tech_sig != "VOLATILE_IGNORE":
                if conf > best_deploy_conf:
                    best_deploy_conf = conf
                    best_deploy_candidate = t
        
        if best_deploy_candidate:
            log_decision(
                best_deploy_candidate,
                "BUY",
                f"Initial Deployment: Best Available Candidate ({best_deploy_conf}%)",
            )
            signals[best_deploy_candidate] = {
                "action": "BUY",
                "reason": "INITIAL_DEPLOYMENT",
                "price": ticker_intel[best_deploy_candidate]["price"],
            }

    # --- Phase 3: Coordinated Execution ---
    print("🚀 Executing Coordinated Trades...")
    execution_results = []

    trading_enabled = os.environ.get("TRADING_ENABLED", "true").lower() == "true"
    is_market_open = signal_agent.is_market_open()
    effective_enabled = trading_enabled and is_market_open

    # 1. Execute SELLs First
    for ticker, sig in signals.items():
        if sig.get("action") == "SELL":
            reason = sig.get("reason", "Strategy Signal")
            if not effective_enabled:
                log_decision(ticker, "SKIP", f"🧊 DRY RUN: Intent SELL ({reason})")
                status = "dry_run_sell"
            else:
                exec_res = execution_manager.place_order(
                    ticker, "SELL", 0, sig["price"], reason=reason
                )
                status = f"executed_{exec_res.get('status', 'FAIL')}"
                log_decision(
                    ticker, "SELL", f"Execution Status: {status} | Reason: {reason}"
                )

            execution_results.append(
                {"ticker": ticker, "signal": "SELL", "status": status, "reason": reason}
            )

    # 2. Execute BUYs
    for ticker, sig in signals.items():
        if sig.get("action") == "BUY":
            reason = sig.get("reason", "Strategy Signal")
            if not effective_enabled:
                log_decision(ticker, "SKIP", f"🧊 DRY RUN: Intent BUY ({reason})")
                status = "dry_run_buy"
            else:
                cash_pool = portfolio_manager.get_cash_balance()
                room_to_buy = total_equity * 0.25 - held_tickers.get(ticker, {}).get(
                    "market_value", 0.0
                )

                base_unit = total_equity * 0.05
                intel = ticker_intel.get(ticker, {})
                sentiment = float(intel.get("sentiment", 0.0))
                multiplier = 1.0 + max(0.0, sentiment)
                allocation = min(base_unit * multiplier, room_to_buy, cash_pool)

                if allocation >= 1000:
                    exec_res = execution_manager.place_order(
                        ticker,
                        "BUY",
                        0,
                        sig["price"],
                        cash_available=allocation,
                        reason=reason,
                    )
                    status = f"executed_{exec_res.get('status', 'FAIL')}"
                    log_decision(
                        ticker,
                        "BUY",
                        f"Execution Status: {status} | Alloc: ${allocation:.2f} | Reason: {reason}",
                    )
                else:
                    log_decision(
                        ticker,
                        "SKIP",
                        f"Insufficient Allocation (${allocation:.2f} < $1000) or Room to Buy.",
                    )
                    status = "skipped_insufficient_funds"

            execution_results.append(
                {"ticker": ticker, "signal": "BUY", "status": status, "reason": reason}
            )

    # Performance Logging
    try:
        from bot.telemetry import log_performance

        final_conv_prices = {t: intel["price"] for t, intel in ticker_intel.items()}
        perf_metrics = portfolio_manager.calculate_total_equity(final_conv_prices)
        log_performance(
            bq_client, f"{PROJECT_ID}.trading_data.performance_logs", perf_metrics
        )
        execution_results.append({"type": "performance_summary", "data": perf_metrics})
    except Exception as e:
        print(f"❌ Perf Log Fail: {e}")

    # --- Phase 4: Post-Trade Reconciliation ---
    # Triggered only if any actual orders were attempted (not just dry-run intent)
    executed_trades = [r for r in execution_results if "executed" in str(r.get("status", ""))]
    
    if executed_trades:
        try:
            print(f"⌛ Waiting 45s for Alpaca fills before reconciliation...")
            await asyncio.sleep(45)
            print("🔄 Triggering Post-Trade Reconciliation...")
            await asyncio.to_thread(reconciler.sync_portfolio)
            await asyncio.to_thread(reconciler.sync_executions)
        except Exception as e:
            print(f"⚠️ Post-Trade Sync Warning: {e}")

    # --- Phase 5: Intraday Reflection ---
    # We do this asynchronously/fire-and-forget ideally, but here we wait to capture logs
    try:
        print("🧠 Running Intraday Hindsight Analysis...")
        await feedback_agent.run_hindsight()
    except Exception as e:
        print(f"⚠️ Feedback Loop Error: {e}")

    return execution_results


from typing import Optional


async def get_latest_confidence(ticker: str) -> Optional[int]:
    """Fetches the latest prediction confidence for a ticker from BQ."""
    print(f"🔍 DEBUG: Running get_latest_confidence v2 for {ticker}")
    query = f"""
        SELECT confidence
        FROM `{PROJECT_ID}.trading_data.ticker_rankings`
        WHERE ticker = '{ticker}'
        AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        ORDER BY timestamp DESC
        LIMIT 1
    """
    try:
        query_job = bq_client.query(query)
        results = query_job.result()
        print(f"DEBUG: Query executed for {ticker}. Rows: {results.total_rows}")
        for row in results:
            print(f"DEBUG: Found confidence for {ticker}: {row.confidence}")
            return row.confidence
        
        print(f"⚠️ No confidence data found for {ticker} in last 24h")
        return 0
    except Exception as e:
        print(f"⚠️ Error fetching confidence for {ticker}: {e}")
    return 0


@app.route("/rank-tickers", methods=["POST"])
async def run_ranker_endpoint():
    """Trigger the morning ticker ranking job."""
    tickers = os.environ.get("BASE_TICKERS", "NVDA,MU,AMD,PLTR,COIN,META,MSTR").split(",")
    try:
        results = await ticker_ranker.rank_and_log(tickers)
        return jsonify({"status": "success", "results": results}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/run-hindsight", methods=["POST"])
async def run_hindsight_endpoint():
    """Trigger the hindsight/reflection job."""
    try:
        await feedback_agent.run_hindsight()
        return (
            jsonify({"status": "success", "message": "Hindsight analysis complete."}),
            200,
        )
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


@app.route("/debug/alpaca/<ticker>")
async def debug_alpaca_endpoint(ticker):
    """Diagnose Alpaca Data connectivity issues on command."""
    log = []
    
    key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_API_SECRET", "")
    
    log.append(f"Key Prefix: {key[:4]}...")
    log.append(f"Secret Length: {len(secret)}")
    
    if not key or not secret:
        return jsonify({"status": "error", "log": log, "message": "Keys missing"}), 500
        
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        
        client = StockHistoricalDataClient(key, secret)
        
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=20) # Short window for speed
        
        # Test 1: IEX Feed
        log.append("Attempting IEX feed...")
        try:
            req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start, end=end, feed="iex")
            bars = client.get_stock_bars(req)
            count = len(bars.data.get(ticker, [])) if bars.data else 0
            log.append(f"IEX Result: {count} bars")
        except Exception as e:
            log.append(f"IEX Failed: {str(e)}")
            
        # Test 2: SIP Feed (if IEX failed or empty)
        log.append("Attempting SIP feed...")
        try:
            req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start, end=end, feed="sip")
            bars = client.get_stock_bars(req)
            count = len(bars.data.get(ticker, [])) if bars.data else 0
            log.append(f"SIP Result: {count} bars")
        except Exception as e:
            log.append(f"SIP Failed: {str(e)}")
            
        return jsonify({"status": "complete", "log": log}), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "fatal", "error": str(e), "log": log}), 500


# --- 5. LOCAL RUNNER ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
