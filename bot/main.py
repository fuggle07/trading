import os
import asyncio
import logging
import finnhub
import pandas as pd
from flask import Flask, jsonify
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from bot.telemetry import log_watchlist_data, log_macro_snapshot, log_decision
import pytz
import traceback
from google.cloud import bigquery
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
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

logger = logging.getLogger(__name__)

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

# Exposure Threshold
MIN_EXPOSURE_THRESHOLD = float(os.environ.get("MIN_EXPOSURE_THRESHOLD", 0.65))
print(f"📊 Minimum Portfolio Exposure Threshold: {MIN_EXPOSURE_THRESHOLD:.1%}")

# Stop-loss cooldown registry — prevents re-entering a position within
# STOP_LOSS_COOLDOWN_MINUTES of a stop being triggered. In-memory: resets on restart.
STOP_LOSS_COOLDOWN_MINUTES = 30
_stop_loss_cooldown: Dict[str, datetime] = {}

# High-water-mark registry — tracks the peak intraday price for each held position.
# Used by the trailing stop logic instead of a hard +5% profit target.
_high_water_marks: Dict[str, float] = {}

# Position entry-time registry — enforces a minimum hold period to prevent
# the bot being shaken out of a good position by short-term noise.
MIN_HOLD_MINUTES = 30
_position_entry_times: Dict[str, datetime] = {}

# Scaled-out registry — tracks positions that have already taken partial profits (50%).
_scaled_out_tickers: set[str] = set()

portfolio_manager = PortfolioManager(bq_client, portfolio_table_id)
execution_manager = ExecutionManager(portfolio_manager)
fundamental_agent = FundamentalAgent(finnhub_client=finnhub_client)
ticker_ranker = TickerRanker(PROJECT_ID, bq_client)
feedback_agent = FeedbackAgent(PROJECT_ID, bq_client)
reconciler = PortfolioReconciler(PROJECT_ID, bq_client)

# --- 2. CORE UTILITIES ---


def _get_ny_time():
    return datetime.now(pytz.timezone("America/New_York"))


# Retrieve Alpaca Keys
ALPACA_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET")

# Alpaca Data Client
stock_historical_client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET) if ALPACA_KEY and ALPACA_SECRET else None


async def fetch_historical_data(ticker):
    """Fetches daily candles for the last 60 days using Alpaca."""
    loop = asyncio.get_event_loop()

    def get_candles():
        if not ALPACA_KEY or not ALPACA_SECRET:
            print(f"⚠️  Alpaca keys missing for {ticker}")
            return None

        try:
            # client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET) # Use global client
            if not stock_historical_client:
                return None

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

            bars = stock_historical_client.get_stock_bars(request_params)

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
        "calendar": [],
        "vix": 0.0,
        "formatted": "Market Context: Stable",
    }

    try:
        # Fetch data in parallel
        indices_task = fundamental_agent.get_market_indices()
        rates_task = fundamental_agent.get_treasury_rates()
        calendar_task = fundamental_agent.get_economic_calendar()
        qqq_sma_task = fundamental_agent.get_index_technicals("QQQ", window=50)

        indices, rates, calendar, qqq_sma50 = await asyncio.gather(
            indices_task, rates_task, calendar_task, qqq_sma_task
        )

        indices = indices or {}
        rates = rates or {}
        calendar = calendar or []
        
        # Add technicals to the indices dict for the signal agent
        indices["qqq_sma50"] = float(qqq_sma50 or 0.0)

        macro_data["indices"] = indices
        macro_data["rates"] = rates
        macro_data["calendar"] = calendar
        
        # Explicit cast and safe retrieval to prevent type comparison errors
        vix_val = indices.get("vix") or indices.get("vix_proxy_vxx") or 0.0
        macro_data["vix"] = float(vix_val)

        parts = []
        if isinstance(indices, dict):
            if indices.get("spy_perf") is not None:
                parts.append(f"SPY: {float(indices['spy_perf']):.2f}%")
            if indices.get("qqq_perf") is not None:
                parts.append(f"QQQ: {float(indices['qqq_perf']):.2f}%")
            
            # Add trend info
            qqq_price = indices.get("qqq_price", 0.0)
            if qqq_price > 0 and qqq_sma50 > 0:
                trend = "Bullish" if qqq_price > qqq_sma50 else "Bearish"
                parts.append(f"Trend: {trend}")
        
        if isinstance(rates, dict) and rates.get("10Y") is not None:
            parts.append(f"10Y Yield: {float(rates['10Y']):.2f}%")
            
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
            result = await sentiment_analyzer.analyze_news(
                ticker, news, lessons, context=context
            )
            sentiment_score, gemini_reasoning = (
                result if isinstance(result, tuple) else (result, "")
            )
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
    tickers_env = os.environ.get("BASE_TICKERS", "TSLA,NVDA,AMD,PLTR,COIN,META,GOOG,MSFT,GOLD,NEM,AMZN,AVGO,CRM,ORCL,LMT")
    base_tickers = [t.strip() for t in tickers_env.split(",") if t.strip()]

    # --- Phase 0: Reconciliation (Source of Truth) ---
    print("🔄 Reconciling Portfolio with Alpaca...")
    try:
        await asyncio.to_thread(reconciler.sync_portfolio)
        await asyncio.to_thread(reconciler.sync_executions)
    except Exception as e:
        print(f"⚠️ Reconciliation Warning: {e}")

    # --- Phase 1: Portfolio Awareness & Intel Gathering ---
    print("🔄 Fetching Portfolio & Intel...")
    held_tickers = portfolio_manager.get_held_tickers()

    # Preliminary Commitment Log (Requested by user to see early in run)
    try:
        if held_tickers and stock_historical_client:
            # Quick quote fetch for just held assets to show commitment
            held_symbols = list(held_tickers.keys())
            early_quotes_req = StockLatestQuoteRequest(symbol_or_symbols=held_symbols)
            early_quotes = stock_historical_client.get_stock_latest_quote(early_quotes_req)
            
            p_market_val = 0.0
            for s, q in early_quotes.items():
                p_market_val += float(held_tickers[s]) * float(q.ask_price)
            
            p_cash = portfolio_manager.get_cash_balance()
            
            # Fetch Account Equity directly from Alpaca for source-of-truth accuracy
            alpaca_account = (await asyncio.to_thread(reconciler.trading_client.get_account)) if reconciler.trading_client else None
            p_equity = float(alpaca_account.equity) if alpaca_account else (p_cash + p_market_val)
            
            p_commitment = (p_market_val / p_equity) * 100 if p_equity > 0 else 0
            
            print(f"📊 Preliminary Commitment: {p_commitment:.1f}% (${p_market_val:,.2f} / ${p_equity:,.2f})")
        else:
            print("📊 Preliminary Commitment: 0.0% (Cash Account)")
    except Exception as e:
        print(f"⚠️ Preliminary commitment check failed: {e}")

    # Audit monitored tickers, held assets, and the hedge reserve (PSQ)
    hedge_ticker = "PSQ"
    tickers = list(set(base_tickers + list(held_tickers.keys()) + [hedge_ticker]))
    print(f"🔍 Starting Multi-Phase Audit for: {tickers}")

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

    # Fetch all quotes in one FMP batch call
    batch_quotes_task = fundamental_agent.get_batch_quotes(tickers)
    earnings_task = fundamental_agent.get_upcoming_earnings(tickers)

    batch_quotes, earnings_calendar = await asyncio.gather(batch_quotes_task, earnings_task)
    logger.info(f"Batch quotes received for {len(batch_quotes)} tickers. Earnings alerts: {len(earnings_calendar)}")

    # Process all tickers in parallel
    await asyncio.gather(
        *[
            process_ticker_intelligence(
                t,
                batch_quotes,
                finnhub_client,
                fundamental_agent,
                macro_data,
                lessons,
                bq_client,
                table_id,
                current_prices,
                ticker_intel,
                held_tickers,
                earnings_calendar,
            )
            for t in tickers
        ]
    )

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
        if intel is None:
            continue
        indicators = intel.get("indicators")
        if indicators:
            total_market_val = val_data.get("total_market_value", 0.0)
            exposure = total_market_val / total_equity if total_equity > 0 else 0.0

            market_data = {
                "ticker": ticker,
                "current_price": intel.get("price", 0.0),
                "sma_20": indicators.get("sma_20", 0.0),
                "sma_50": indicators.get("sma_50", 0.0),
                "bb_upper": indicators.get("bb_upper", 0.0),
                "bb_lower": indicators.get("bb_lower", 0.0),
                "sentiment_score": intel.get("sentiment", 0.0),
                "is_healthy": intel.get("is_healthy", True),
                "health_reason": intel.get("health_reason", ""),
                "is_deep_healthy": intel.get("is_deep_healthy", True),
                "deep_health_reason": intel.get("deep_health_reason", ""),
                "f_score": intel.get("f_score", 0),
                "rsi": intel.get("rsi") if intel.get("rsi") is not None else 50.0,
                "avg_price": held_tickers.get(ticker, {}).get("avg_price", 0.0),
                "hwm": _high_water_marks.get(ticker, 0.0),
                "prediction_confidence": intel.get("confidence", 0),
                "is_low_exposure": exposure < MIN_EXPOSURE_THRESHOLD,
                "band_width": float(intel.get("band_width", 0.0)),
                "vix": float(macro_data.get("vix", 0.0)),
                "volume": intel.get("volume", 0.0),
                "avg_volume": intel.get("avg_volume", 1.0),
                "days_to_earnings": earnings_calendar.get(ticker) if earnings_calendar else None,
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
    weakest_link_effective_conf = 999  # Track blended score for tie-breaking

    # 1. Identify Weakest Link (Lowest Confidence OR Failed Fundamentals OR Sentiment Collapse)
    for t in held_tickers:
        intel = ticker_intel.get(t)
        if intel is None:
            continue
        conf = intel.get("confidence", 0)
        is_deep = intel.get("is_deep_healthy", True)
        sentiment = float(intel.get("sentiment", 0.0))

        # Blended effective confidence: sentiment adjusts the score by up to ±15
        sentiment_bonus = max(-15, min(15, int(sentiment * 20)))
        effective_conf = conf + sentiment_bonus

        # SWAP TRIGGER: Low blended confidence, failed fundamentals, OR acute sentiment collapse
        sentiment_collapse = sentiment < -0.3  # news has turned toxic right now
        is_weak = effective_conf < 50 or not is_deep or sentiment_collapse

        if is_weak:
            # Prioritise: fundamental failure > sentiment collapse > low confidence
            if weakest_link is None:
                weakest_link = t
                weakest_link_effective_conf = effective_conf
            else:
                current_is_deep = ticker_intel[weakest_link].get("is_deep_healthy", True)
                current_sent = float(ticker_intel[weakest_link].get("sentiment", 0.0))
                current_sent_collapse = current_sent < -0.3

                # Fundamental failure always wins
                if current_is_deep and not is_deep:
                    weakest_link = t
                    weakest_link_effective_conf = effective_conf
                # Both fundamental failures — pick lower blended conf
                elif not current_is_deep and not is_deep:
                    if effective_conf < weakest_link_effective_conf:
                        weakest_link = t
                        weakest_link_effective_conf = effective_conf
                # Sentiment collapse beats purely low-confidence
                elif not current_sent_collapse and sentiment_collapse:
                    weakest_link = t
                    weakest_link_effective_conf = effective_conf
                # Same tier — pick lower blended confidence
                elif effective_conf < weakest_link_effective_conf:
                    weakest_link = t
                    weakest_link_effective_conf = effective_conf

    # 2. Identify Rising Star (Highest Blended Conviction across ALL tickers)
    # Exclude the weakest_link itself (can't sell and re-buy the same ticker).
    # Uses effective_conf = confidence + sentiment bonus (±15) so high-sentiment
    # stocks surface faster and negative-narrative stocks are penalised.
    rising_star = None
    best_star_effective_conf = 0

    for t in ticker_intel:
        if t == weakest_link:
            continue  # Can't be your own rising star

        intel = ticker_intel.get(t)
        if intel is None:
            continue

        conf = intel.get("confidence", 0)
        sentiment = float(intel.get("sentiment", 0.0))
        sentiment_bonus = max(-15, min(15, int(sentiment * 20)))
        effective_conf = conf + sentiment_bonus

        # Candidate Check: Must pass blended threshold
        if effective_conf > 75:
            if rising_star is None or effective_conf > best_star_effective_conf:
                rising_star = t
                best_star_effective_conf = effective_conf

    # 3. Evaluate Swap
    if rising_star and weakest_link:
        weakest_conf = ticker_intel[weakest_link].get("confidence", 0)
        star_intel = ticker_intel[rising_star]

        should_swap = signal_agent.check_conviction_swap(
            weakest_link,
            weakest_link_effective_conf,
            rising_star,
            best_star_effective_conf,
            potential_fundamentals={
                "is_deep_healthy": star_intel["is_deep_healthy"],
                "f_score": star_intel["f_score"],
            },
        )

        if should_swap:
            weakest_conf = ticker_intel[weakest_link].get("confidence", 0)
            log_decision(
                rising_star,
                "SWAP",
                f"Rotating out of {weakest_link} (eff:{weakest_link_effective_conf}) into {rising_star} (eff:{best_star_effective_conf})",
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
    elif exposure < MIN_EXPOSURE_THRESHOLD and rising_star:
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

        if is_valid_candidate and (
            rising_star not in signals or signals[rising_star]["action"] != "BUY"
        ):
            # Check for volatility
            if tech_signal == "VOLATILE_IGNORE":
                logger.debug(f"Initial Deployment: Skipping {rising_star} due to high volatility.")
            elif existing_action == "SELL":
                logger.debug(f"Initial Deployment: Skipping {rising_star} due to SELL signal.")
            else:
                log_decision(
                    rising_star,
                    "BUY",
                    f"Initial Deployment: High Conviction Rising Star (eff:{best_star_effective_conf})",
                )
                signals[rising_star] = {
                    "action": "BUY",
                    "reason": "INITIAL_DEPLOYMENT",
                    "price": ticker_intel[rising_star]["price"],
                }


    # --- Phase 3: Coordinated Execution ---
    print("🚀 Executing Coordinated Trades...")
    execution_results = []

    trading_enabled = os.environ.get("TRADING_ENABLED", "true").lower() == "true"
    is_market_open = signal_agent.is_market_open()
    effective_enabled = trading_enabled and is_market_open

    # 1. Execute SELLs First
    for ticker_obj, sig in signals.items():
        ticker = str(ticker_obj)
        action = str(sig.get("action"))
        
        if action in ["SELL", "SELL_ALL", "SELL_PARTIAL_50"]:
            reason = str(sig.get("reason", "Strategy Signal"))
            
            # Extract position data
            pos = held_tickers.get(ticker, {})
            position_val = float(pos.get("market_value", 0.0))
            current_qty = float(pos.get("qty", 0))

            # Determine sell quantity
            is_partial = action == "SELL_PARTIAL_50"
            target_qty = 0 # Default to SELL ALL
            
            if is_partial:
                # Scaled-out logic: sell 50%
                target_qty = int(current_qty * 0.5)
                # Safety: if we have shares but 50% is 0 (e.g. 1 share), sell at least 1
                if target_qty == 0 and current_qty > 0:
                    target_qty = int(current_qty)

            # 1. Minimum Hold Time Guard — block non-emergency SELLs if held < 30m
            # Emergency = Stop Loss, Sentiment Collapse, RSI, or Trailing Stop
            entry_time = _position_entry_times.get(ticker)
            is_emergency = any(k in reason for k in ["STOP_LOSS", "SENTIMENT", "RSI", "TRAILING_STOP", "EXIT_SELL_ALL"])
            
            if entry_time and not is_emergency and not is_partial:
                hold_duration = (datetime.now() - entry_time).total_seconds() / 60
                if hold_duration < MIN_HOLD_MINUTES:
                    log_decision(ticker, "SKIP", f"Churn Guard: Hold time {hold_duration:.1f}m < {MIN_HOLD_MINUTES}m")
                    continue

            if not effective_enabled:
                sell_val = position_val * 0.5 if is_partial else position_val
                log_decision(ticker, action, f"🧊 DRY RUN: Intent {action} ${sell_val:,.2f} ({reason})")
                status = f"dry_run_{action.lower()}"
            else:
                exec_res = execution_manager.place_order(
                    ticker, "SELL", target_qty, sig["price"], reason=reason
                )
                status = f"executed_{exec_res.get('status', 'FAIL')}"
                log_decision(
                    ticker, action, f"Execution Status: {status} | Value: ${position_val:,.2f} | Reason: {reason}"
                )

            # Registry Updates
            if "executed" in status:
                if is_partial:
                    _scaled_out_tickers.add(ticker)
                else:
                    # Full exit: Clear all tracking data for this position
                    _high_water_marks.pop(ticker, None)
                    _position_entry_times.pop(ticker, None)
                    _scaled_out_tickers.discard(ticker)

            # Record stop-loss cooldown if it was a negative exit
            if "STOP_LOSS" in reason or "SENTIMENT" in reason:
                _stop_loss_cooldown[ticker] = datetime.now(timezone.utc) + timedelta(
                    minutes=STOP_LOSS_COOLDOWN_MINUTES
                )

            execution_results.append(
                {"ticker": ticker, "signal": action, "status": status, "reason": reason}
            )

    # 1.5 Portfolio Hedge Check
    # If market is bearish or VIX is high, we buy inverse ETFs (e.g., PSQ)
    hedge_ticker = "PSQ"
    hedge_action, target_pct = signal_agent.evaluate_macro_hedge(macro_data)
    
    current_hedge_pos = held_tickers.get(hedge_ticker, {})
    current_hedge_val = float(current_hedge_pos.get("market_value", 0.0))
    target_hedge_val = total_equity * target_pct
    
    if hedge_action == "BUY_HEDGE":
        # Check if we need to enter OR top up (if current is significantly below target)
        # We top up if target is more than 20% higher than current (to avoid tiny churn)
        needs_entry = hedge_ticker not in held_tickers
        needs_topup = current_hedge_val < (target_hedge_val * 0.8)
        
        if needs_entry or needs_topup:
            order_val = target_hedge_val - current_hedge_val
            if effective_enabled:
                exec_res = execution_manager.place_order(
                    hedge_ticker, "BUY", 0, 0.0, # Market buy
                    reason=f"MACRO_HEDGE_{int(target_pct*100)}PCT_TRIGGERED",
                    cash_available=float(order_val)
                )
                log_decision(hedge_ticker, "BUY", f"Hedge Scaling: Target {target_pct:.0%} | Scaling Order ${order_val:,.2f}")
            else:
                log_decision(hedge_ticker, "BUY", f"🧊 DRY RUN: Hedge Scaling Target {target_pct:.0%} | Order ${order_val:,.2f}")
            
    elif hedge_action == "CLEAR_HEDGE" and hedge_ticker in held_tickers:
        if effective_enabled:
            exec_res = execution_manager.place_order(
                hedge_ticker, "SELL", 0, 0.0, # Sell all
                reason="MACRO_HEDGE_CLEARED"
            )
            log_decision(hedge_ticker, "SELL", f"Hedging Cleared: {exec_res.get('status', 'FAIL')}")
        else:
            log_decision(hedge_ticker, "SELL", "🧊 DRY RUN: Hedging Cleared")

    # 2. Execute BUYs
    # Exposure tracking to respect 65% baseline vs Star Reserve
    running_exposure = exposure

    for ticker, sig in signals.items():
        if sig.get("action") == "BUY":
            reason = sig.get("reason", "Strategy Signal")
            is_star = sig.get("meta", {}).get("is_star", False)
            vix = float(macro_data.get("vix", 0.0))

            # 1. Stop-loss cooldown guard — skip re-entry within 30 min of a stop
            cooldown_until = _stop_loss_cooldown.get(ticker)
            if cooldown_until is not None and datetime.now(timezone.utc) < cooldown_until:
                remaining = int(
                    (cooldown_until - datetime.now(timezone.utc)).total_seconds() / 60
                )
                log_decision(
                    ticker, "SKIP", f"Stop-loss cooldown active ({remaining}m remaining)"
                )
                continue

            # 2. Morning Volatility Gate — block non-emergency BUYs before 10:00 AM ET
            # High bid-ask spreads and erratic price discovery in the first 30 mins.
            now_et = datetime.now(pytz.timezone("America/New_York"))
            if now_et.hour == 9 and now_et.minute >= 30:
                if not is_star and reason != "CONVICTION_ROTATION":
                    log_decision(ticker, "SKIP", f"Morning Volatility Gate Active (until 10:00 AM ET)")
                    continue

            # 2. VIX guard — block speculative INITIAL_DEPLOYMENT when fear is elevated
            if vix > 25 and reason == "INITIAL_DEPLOYMENT":
                log_decision(ticker, "SKIP", f"VIX={vix:.1f} > 25: Blocking new deployment in high-fear market")
                continue

            # 65/35 Allocation Strategy
            # If exposure >= 65%, only allow BUY if ticker is "Star Rated"
            if running_exposure >= 0.65 and not is_star:
                log_decision(
                    ticker, 
                    "SKIP", 
                    f"Baseline Exposure Hit ({running_exposure:.1%}). {ticker} is not 'Star Rated'."
                )
                continue

            # Calculate Allocation
            cash_pool = float(portfolio_manager.get_cash_balance())
            already_held_value = float(held_tickers.get(ticker, {}).get("market_value", 0.0))
            
            # Fetch intelligence for sizing math
            intel = ticker_intel.get(ticker)
            if intel is None:
                log_decision(ticker, "SKIP", "Missing intelligence data during execution phase")
                continue

            sentiment = float(intel.get("sentiment", 0.0))

            # Tiered Automated Position Sizing:
            # We calculate a dynamic target allocation based on conviction, VIX, and volatility.
            target_allocation = signal_agent.calculate_position_size(
                total_equity,
                sig.get("conviction", 0),
                vix=vix,
                band_width=intel.get("band_width", 0.03),
                is_star=is_star
            )

            # Buy amount = Target Allocation - Current Holdings
            allocation = max(0, target_allocation - already_held_value)

            # Cap Check: Respect the 65% baseline for non-Stars
            if not is_star:
                room_to_exposure_target = float(max(
                    0.0, total_equity * 0.65 - total_equity * running_exposure
                ))
                allocation = float(min(allocation, room_to_exposure_target))
            
            # Final liquidity check
            allocation = min(allocation, cash_pool)

            if not effective_enabled:
                if allocation >= 1000:
                    star_prefix = "⭐ STAR: " if is_star else ""
                    log_decision(ticker, "BUY", f"🧊 DRY RUN: {star_prefix}Intent BUY ${allocation:,.2f} ({reason})")
                    status = "dry_run_buy"
                    # Update running exposure for logic flow
                    running_exposure += (allocation / total_equity) if total_equity > 0 else 0
                else:
                    log_decision(ticker, "SKIP", f"🧊 DRY RUN: Intent BUY rejected (Insufficient Allocation ${allocation:.2f} < $1000)")
                    status = "skipped_insufficient_funds"
            else:
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
                    star_prefix = "⭐ STAR: " if is_star else ""
                    log_decision(
                        ticker,
                        "BUY",
                        f"Execution Status: {status} | {star_prefix}Alloc: ${allocation:.2f} | Reason: {reason}",
                    )
                    running_exposure += (allocation / total_equity) if total_equity > 0 else 0
                else:
                    log_decision(
                        ticker,
                        "SKIP",
                        f"Insufficient Allocation (${allocation:.2f} < $1000) or Room to Buy.",
                    )
                    status = "skipped_insufficient_funds"

            if "executed" in status:
                _position_entry_times[ticker] = datetime.now(timezone.utc)

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
    executed_trades = [
        r for r in execution_results if "executed" in str(r.get("status", ""))
    ]

    if executed_trades:
        try:
            print("⌛ Waiting 45s for Alpaca fills before reconciliation...")
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


async def get_latest_confidence(ticker: str) -> Optional[int]:
    """Fetches the latest prediction confidence for a ticker from BQ ticker_rankings table."""
    query = f"""
        SELECT confidence
        FROM `{PROJECT_ID}.trading_data.ticker_rankings`
        WHERE ticker = '{ticker}'
        AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        ORDER BY timestamp DESC
        LIMIT 1
    """
    try:
        results = bq_client.query(query).result()
        for row in results:
            return row.confidence
        return 0
    except Exception as e:
        logger.warning(f"[{ticker}] Could not fetch confidence score: {e}")
    return 0


@app.route("/rank-tickers", methods=["POST"])
async def run_ranker_endpoint():
    """Trigger the morning ticker ranking job."""
    base = os.environ.get("BASE_TICKERS", "TSLA,NVDA,AMD,PLTR,COIN,META,GOOG,MSFT,GOLD,NEM,AMZN,AVGO,CRM,ORCL,LMT").split(",")
    held = list(portfolio_manager.get_held_tickers().keys())
    tickers = list(set(base + held))
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


@app.route("/equity")
def equity_snapshot():
    """
    Returns live portfolio equity calculated directly from BigQuery.
    Bypasses performance_logs cache — always reflects the latest state.
    """
    try:
        # 1. Fetch all portfolio rows
        query = f"""
            SELECT asset_name, holdings, cash_balance, avg_price, last_updated
            FROM `{portfolio_table_id}`
            ORDER BY asset_name
        """
        rows = list(bq_client.query(query).result())

        # 2. Get latest prices from watchlist_logs for held tickers
        price_query = f"""
            SELECT ticker, price
            FROM (
                SELECT ticker, price,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY timestamp DESC) as rn
                FROM `{table_id}`
            )
            WHERE rn = 1
        """
        price_rows = list(bq_client.query(price_query).result())
        latest_prices = {{r.ticker: float(r.price) for r in price_rows}}

        # 3. Build breakdown
        total_cash = 0.0
        total_market_value = 0.0
        positions = []

        for row in rows:
            ticker = row.asset_name
            if ticker == "USD":
                total_cash = float(row.cash_balance)
                continue

            holdings = float(row.holdings)
            avg_price = float(row.avg_price or 0)
            current_price = latest_prices.get(ticker, 0.0)
            market_value = holdings * current_price
            cost_basis = holdings * avg_price
            unrealized_pnl = market_value - cost_basis

            if holdings > 0:
                total_market_value += market_value
                positions.append({
                    "ticker": ticker,
                    "holdings": holdings,
                    "avg_price": round(avg_price, 4),
                    "current_price": round(current_price, 4),
                    "market_value": round(market_value, 2),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "last_updated": row.last_updated.isoformat() if row.last_updated else None,
                })

        total_equity = total_cash + total_market_value
        exposure_pct = (total_market_value / total_equity * 100) if total_equity > 0 else 0.0

        return jsonify({
            "total_equity_usd": round(total_equity, 2),
            "total_cash_usd": round(total_cash, 2),
            "total_market_value_usd": round(total_market_value, 2),
            "exposure_pct": round(exposure_pct, 1),
            "positions": positions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return (
        jsonify(
            {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
        ),
        200,
    )


async def process_ticker_intelligence(
    ticker,
    batch_quotes,
    finnhub_client,
    fundamental_agent,
    macro_data,
    lessons,
    bq_client,
    table_id,
    current_prices,
    ticker_intel,
    held_tickers,
    earnings_calendar,
):
    print(f"[{ticker}] 📡 Gathering Intel for {ticker}...")
    try:
        # Quote: use pre-fetched batch result; fall back to Finnhub if missing
        res_quote = batch_quotes.get(ticker)
        if not res_quote and finnhub_client:
            try:
                res_quote = await asyncio.to_thread(finnhub_client.quote, ticker)
            except Exception:
                res_quote = None

        intelligence_task = fundamental_agent.get_intelligence_metrics(ticker)
        deep_health_task = fundamental_agent.evaluate_deep_health(ticker)
        history_task = fetch_historical_data(ticker)
        confidence_task = get_latest_confidence(ticker)

        # FMP Technical Indicators
        sma20_task = fundamental_agent.get_technical_indicator(ticker, "sma", period=20)
        sma50_task = fundamental_agent.get_technical_indicator(ticker, "sma", period=50)
        rsi_task = fundamental_agent.get_technical_indicator(ticker, "rsi", period=14)
        std_task = fundamental_agent.get_technical_indicator(
            ticker, "standarddeviation", period=20
        )

        # Execute gather with error handling (quote already resolved above)
        intel_results = await asyncio.gather(
            intelligence_task,
            deep_health_task,
            history_task,
            confidence_task,
            sma20_task,
            sma50_task,
            rsi_task,
            std_task,
            return_exceptions=True,
        )

        res_intel = (
            intel_results[0] if not isinstance(intel_results[0], Exception) else {}
        )
        res_consolidated_health = (
            intel_results[1]
            if not isinstance(intel_results[1], Exception)
            else (False, "Health fail", False, "Deep fail", None)
        )
        res_history = (
            intel_results[2] if not isinstance(intel_results[2], Exception) else None
        )
        res_conf = intel_results[3] if not isinstance(intel_results[3], Exception) else 0
        res_sma20 = (
            intel_results[4] if not isinstance(intel_results[4], Exception) else None
        )
        res_sma50 = (
            intel_results[5] if not isinstance(intel_results[5], Exception) else None
        )
        res_rsi = (
            intel_results[6] if not isinstance(intel_results[6], Exception) else None
        )
        res_std = (
            intel_results[7] if not isinstance(intel_results[7], Exception) else None
        )
        
        # Initialize defaults to prevent NameErrors if res_quote fails
        price = 0.0
        volume = 0.0
        avg_volume = 1.0
        sentiment_score = 0.0
        gemini_reasoning = "N/A"

        if res_quote and isinstance(res_quote, dict) and "c" in res_quote:
            price = float(res_quote["c"])
            volume = float(res_quote.get("v", 0))
            avg_volume = float(res_quote.get("av", 1))
            current_prices[ticker] = price

            # Update high-water-mark for held positions (used by trailing stop)
            if ticker in held_tickers and price > 0:
                current_hwm = _high_water_marks.get(ticker, 0.0)
                if price > current_hwm:
                    _high_water_marks[ticker] = price

            # --- PREPARE ENRICHED CONTEXT FOR AI ---
            sma20_val = float(res_sma20.get("sma", 0)) if res_sma20 else 0
            sma_stretch = ((price / sma20_val) - 1) * 100 if sma20_val > 0 else 0

            ai_context = {
                "macro": macro_data,
                "analyst_consensus": res_intel.get("analyst_consensus", "Neutral"),
                "institutional_flow": res_intel.get("institutional_momentum", "Neutral"),
                "insider_momentum": res_intel.get("insider_momentum", "N/A"),
                "rsi": float(res_rsi.get("rsi", 50)) if res_rsi else 50.0,
                "sma_stretch_pct": round(sma_stretch, 2),
            }

            sentiment_result = await fetch_sentiment(ticker, lessons, context=ai_context)
            sentiment_score, gemini_reasoning = (
                sentiment_result
                if isinstance(sentiment_result, tuple)
                else (sentiment_result, "")
            )

        # 1. Technical Baseline Construction
        indicators = calculate_technical_indicators(res_history, ticker) or {}
        
        # Override derived indicators with real-time FMP technical endpoints if available
        if res_sma20 and isinstance(res_sma20, dict):
            indicators["sma_20"] = float(res_sma20.get("sma", indicators.get("sma_20", 0)))
        if res_sma50 and isinstance(res_sma50, dict):
            indicators["sma_50"] = float(res_sma50.get("sma", indicators.get("sma_50", 0)))
        
        if res_sma20 and isinstance(res_sma20, dict) and res_std and isinstance(res_std, dict):
            sma = float(res_sma20.get("sma", 0))
            std = float(res_std.get("standardDeviation", 0))
            if sma > 0:
                indicators["bb_upper"] = sma + (std * 2)
                indicators["bb_lower"] = sma - (std * 2)

        is_h, h_re, is_d, d_re, f_sc = res_consolidated_health

        # Calculate Band Width as a volatility metric
        bw = 0.0
        if indicators.get("bb_upper") and indicators.get("bb_lower") and price > 0:
            bw = float((indicators["bb_upper"] - indicators["bb_lower"])) / float(price)

        ticker_intel[ticker] = {
            "price": price,
            "sentiment": sentiment_score,
            "is_healthy": is_h,
            "health_reason": h_re,
            "is_deep_healthy": is_d,
            "deep_health_reason": d_re,
            "f_score": f_sc,
            "confidence": int(res_conf or 0),
            "indicators": indicators,
            "history_res": res_history,
            "rsi": float(res_rsi.get("rsi", 0)) if (res_rsi and isinstance(res_rsi, dict)) else None,
            "volume": volume if 'volume' in locals() else 0.0,
            "avg_volume": avg_volume if 'avg_volume' in locals() else 1.0,
            "band_width": bw,
            "hwm": _high_water_marks.get(ticker, 0.0),
            "has_scaled_out": (ticker in _scaled_out_tickers),
        }

        # Log to Watchlist — include all technical fields
        log_watchlist_data(
            bq_client,
            table_id,
            ticker,
            price,
            sentiment_score,
            int(res_conf or 0),
            rsi=float(res_rsi.get("rsi", 0)) if (res_rsi and isinstance(res_rsi, dict)) else None,
            sma_20=indicators.get("sma_20"),
            sma_50=indicators.get("sma_50"),
            bb_upper=indicators.get("bb_upper"),
            bb_lower=indicators.get("bb_lower"),
            f_score=f_sc,
            conviction=int(res_conf or 0),
            gemini_reasoning=gemini_reasoning,
        )
    except Exception as e:
        print(f"[{ticker}] \u26a0\ufe0f Failed to gather intel for {ticker}: {e}")

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
        start = end - timedelta(days=20)  # Short window for speed

        # Test 1: IEX Feed
        log.append("Attempting IEX feed...")
        try:
            req = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed="iex",
            )
            bars = client.get_stock_bars(req)
            count = len(bars.data.get(ticker, [])) if bars.data else 0
            log.append(f"IEX Result: {count} bars")
        except Exception as e:
            log.append(f"IEX Failed: {str(e)}")

        # Test 2: SIP Feed (if IEX failed or empty)
        log.append("Attempting SIP feed...")
        try:
            req = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed="sip",
            )
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
