import os
import asyncio
import httpx
import logging
from flask import Flask, jsonify
from google.cloud import bigquery
from portfolio_manager import PortfolioManager
from telemetry import log_performance, log_watchlist_data

app = Flask(__name__)

# Configure Logging for high-resolution visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SYSTEM CONFIGURATION
SIMULATED_TICKER = "QQQ"
SIMULATED_SHARES = 100 
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "PLTR", "ARM"]

# Infrastructure Constants
# Using GOOGLE_CLOUD_PROJECT as the primary anchor for BigQuery client and table IDs
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "unified-aberfeldie-node") 
DATASET_ID = "trading_data"
PORTFOLIO_TABLE = f"{PROJECT_ID}.{DATASET_ID}.portfolio"
FINANCE_SERVICE_URL = os.getenv("FINANCE_SERVICE_URL", "http://localhost:8081")
SENTIMENT_SERVICE_URL = os.getenv("SENTIMENT_SERVICE_URL", "http://localhost:8082")

@app.route("/run", methods=["POST"])
async def run_bot():
    """Main entry point for the stateful nightly trading logic."""
    bq_client = bigquery.Client(project=PROJECT_ID)
    pm = PortfolioManager(bq_client, PORTFOLIO_TABLE)
    
    # 1. ANALYZE CURRENT STATE: Query BigQuery for persistent cash and holdings
    try:
        portfolio = pm.get_state(SIMULATED_TICKER)
        current_cash = portfolio['cash_balance']
        current_holdings = portfolio['holdings']
    except Exception as e:
        logger.error(f"Failed to retrieve portfolio state: {e}")
        return jsonify({"status": "error", "message": "Ledger unavailable"}), 500

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 2. DATA INGESTION: Fetch market and sentiment data concurrently
        price_tasks = [client.get(f"{FINANCE_SERVICE_URL}/price/{t}") for t in WATCHLIST]
        sentiment_tasks = [client.get(f"{SENTIMENT_SERVICE_URL}/sentiment/{t}") for t in WATCHLIST]
        
        price_res = await asyncio.gather(*price_tasks, return_exceptions=True)
        sentiment_res = await asyncio.gather(*sentiment_tasks, return_exceptions=True)
        
        # 3. LOGIC HUB: Process results into lookups to avoid index mismatches
        watchlist_rows = []
        sentiment_lookup = {}
        price_lookup = {}

        for i, ticker in enumerate(WATCHLIST):
            # Safe JSON parsing with error handling for task exceptions
            p_data = price_res[i].json() if not isinstance(price_res[i], Exception) else {}
            s_data = sentiment_res[i].json() if not isinstance(sentiment_res[i], Exception) else {}
            
            score = s_data.get("score", 0)
            price = p_data.get("price", 0)
            
            sentiment_lookup[ticker] = score
            price_lookup[ticker] = price

            watchlist_rows.append({
                "ticker": ticker,
                "price": price,
                "fx_rate": p_data.get("fx_rate"),
                "sentiment_score": score,
                "timestamp": bigquery.dbapi.Timestamp.now()
            })

        # 4. THE BET: Decision logic for the target asset
        target_sentiment = sentiment_lookup.get(SIMULATED_TICKER, 0)
        target_price = price_lookup.get(SIMULATED_TICKER, 0)
        action = "IDLE"
        
        # LOGIC A: THE ENTRY (BUY) - Positive Edge + Capital Check
        if target_sentiment > 0.5:
            trade_cost = target_price * SIMULATED_SHARES
            if current_cash >= trade_cost:
                action = "BUY"
                current_cash -= trade_cost
                current_holdings += SIMULATED_SHARES
                pm.update_ledger(SIMULATED_TICKER, current_cash, current_holdings)
            else:
                logger.warning(f"Edge detected for {SIMULATED_TICKER}, but insufficient funds: ${current_cash:.2f}")

        # LOGIC B: THE EXIT (SELL/LIQUIDATE) - Edge Lost + Holdings Check
        elif target_sentiment < 0.5 and current_holdings > 0:
            action = "SELL"
            sale_proceeds = target_price * current_holdings
            current_cash += sale_proceeds
            current_holdings = 0
            pm.update_ledger(SIMULATED_TICKER, current_cash, current_holdings)
            logger.info(f"Exited {SIMULATED_TICKER} position for ${sale_proceeds:.2f}")

        # 5. TELEMETRY: Record results for the final audit
        log_watchlist_data(bq_client, f"{PROJECT_ID}.{DATASET_ID}.tickers", watchlist_rows)
        
        log_performance({
            "ticker": SIMULATED_TICKER,
            "action": action,
            "shares": SIMULATED_SHARES if action == "BUY" else current_holdings,
            "cash_remaining": current_cash
        })

        return jsonify({
            "status": "success",
            "action": action,
            "balance": current_cash,
            "holdings": current_holdings
        }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

