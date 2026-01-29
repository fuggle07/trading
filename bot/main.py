import os
import asyncio
import httpx
import logging
from flask import Flask, jsonify
from google.cloud import bigquery
from portfolio_manager import PortfolioManager
from telemetry import log_performance, log_watchlist_data

app = Flask(__name__)

# Configure Logging for high-resolution visibility in Cloud Run
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SYSTEM CONFIGURATION
SIMULATED_TICKER = "QQQ"
SIMULATED_SHARES = 100 
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "PLTR", "ARM"]

# Infrastructure Constants
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATASET_ID = "trading_data"
PORTFOLIO_TABLE = f"{PROJECT_ID}.{DATASET_ID}.portfolio"
FINANCE_SERVICE_URL = os.getenv("FINANCE_SERVICE_URL", "http://localhost:8081")
SENTIMENT_SERVICE_URL = os.getenv("SENTIMENT_SERVICE_URL", "http://localhost:8082")

@app.route("/run", methods=["POST"])
async def run_bot():
    """Main entry point for the stateful nightly trading logic."""
    bq_client = bigquery.Client()
    pm = PortfolioManager(bq_client, PORTFOLIO_TABLE)
    
    # 1. ANALYZE CURRENT STATE: Query BigQuery for persistent cash and holdings
    portfolio = pm.get_state(SIMULATED_TICKER)
    current_cash = portfolio['cash_balance']
    current_holdings = portfolio['holdings']

    async with httpx.AsyncClient() as client:
        # 2. DATA INGESTION: Fetch market and sentiment data concurrently
        price_tasks = [client.get(f"{FINANCE_SERVICE_URL}/price/{t}") for t in WATCHLIST]
        sentiment_tasks = [client.get(f"{SENTIMENT_SERVICE_URL}/sentiment/{t}") for t in WATCHLIST]
        
        price_res = await asyncio.gather(*price_tasks)
        sentiment_res = await asyncio.gather(*sentiment_tasks)
        
        prices = [r.json() for r in price_res]
        sentiments = [r.json() for r in sentiment_res]
        
        # 3. LOGIC HUB: Process results and identify the "Edge"
        watchlist_rows = []
        sentiment_score = 0
        ticker_price = 0

        for i, ticker in enumerate(WATCHLIST):
            score = sentiments[i].get("score", 0)
            price = prices[i].get("price", 0)
            
            watchlist_rows.append({
                "ticker": ticker,
                "price": price,
                "fx_rate": prices[i].get("fx_rate"),
                "sentiment_score": score,
                "timestamp": bigquery.dbapi.Timestamp.now()
            })

            if ticker == SIMULATED_TICKER:
                sentiment_score = score
                ticker_price = price

        # 4. THE BET: Entry and Exit logic based on the David Walsh model
        action = "IDLE"
        
        # LOGIC A: THE ENTRY (BUY) - Positive Edge + Available Capital
        if sentiment_score > 0.5:
            trade_cost = ticker_price * SIMULATED_SHARES
            if current_cash >= trade_cost:
                action = "BUY"
                current_cash -= trade_cost
                current_holdings += SIMULATED_SHARES
                pm.update_ledger(SIMULATED_TICKER, current_cash, current_holdings)
            else:
                logger.warning(f"Edge detected for {SIMULATED_TICKER}, but insufficient cash: ${current_cash:.2f}")

        # LOGIC B: THE EXIT (SELL) - Edge Lost + Existing Holdings
        elif sentiment_score < 0.5 and current_holdings > 0:
            action = "SELL"
            sale_proceeds = ticker_price * current_holdings
            current_cash += sale_proceeds
            current_holdings = 0
            pm.update_ledger(SIMULATED_TICKER, current_cash, current_holdings)
            logger.info(f"Exited {SIMULATED_TICKER} position for ${sale_proceeds:.2f}")

        # 5. TELEMETRY: Record the run for the final audit
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

