import os
import asyncio
import httpx
from flask import Flask, jsonify
from google.cloud import bigquery
from portfolio_manager import PortfolioManager
from telemetry import log_audit, log_watchlist_data, log_performance

app = Flask(__name__)

# SYSTEM CONFIGURATION
SIMULATED_TICKER = "QQQ"
SIMULATED_SHARES = 100 
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "PLTR", "ARM"]

# Infrastructure Constants
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "unified-aberfeldie-node")
DATASET_ID = "trading_data"
PORTFOLIO_TABLE = f"{PROJECT_ID}.{DATASET_ID}.portfolio"
FINANCE_SERVICE_URL = os.getenv("FINANCE_SERVICE_URL", "http://localhost:8081")
SENTIMENT_SERVICE_URL = os.getenv("SENTIMENT_SERVICE_URL", "http://localhost:8082")

@app.route("/run", methods=["POST"])
async def run_bot():
    bq_client = bigquery.Client(project=PROJECT_ID)
    pm = PortfolioManager(bq_client, PORTFOLIO_TABLE)
    
    log_audit("STARTUP", f"Bot cycle initiated for {SIMULATED_TICKER}")

    # 1. ANALYZE CURRENT STATE
    try:
        portfolio = pm.get_state(SIMULATED_TICKER)
        current_cash = portfolio['cash_balance']
        current_holdings = portfolio['holdings']
        log_audit("STATE", "Portfolio retrieved", {"cash": current_cash, "shares": current_holdings})
    except Exception as e:
        log_audit("CRITICAL", f"Ledger unreachable: {e}")
        return jsonify({"status": "error", "message": "Portfolio offline"}), 500

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 2. DATA INGESTION
        log_audit("INGEST", "Fetching market and sentiment data")
        price_tasks = [client.get(f"{FINANCE_SERVICE_URL}/price/{t}") for t in WATCHLIST]
        sentiment_tasks = [client.get(f"{SENTIMENT_SERVICE_URL}/sentiment/{t}") for t in WATCHLIST]
        
        price_res = await asyncio.gather(*price_tasks, return_exceptions=True)
        sentiment_res = await asyncio.gather(*sentiment_tasks, return_exceptions=True)
        
        # 3. LOGIC HUB
        watchlist_rows = []
        sentiment_map = {}
        price_map = {}

        for i, ticker in enumerate(WATCHLIST):
            p_data = price_res[i].json() if not isinstance(price_res[i], Exception) else {}
            s_data = sentiment_res[i].json() if not isinstance(sentiment_res[i], Exception) else {}
            
            sentiment_map[ticker] = s_data.get("score", 0)
            price_map[ticker] = p_data.get("price", 0)

            watchlist_rows.append({
                "ticker": ticker,
                "price": price_map[ticker],
                "fx_rate": p_data.get("fx_rate"),
                "sentiment_score": sentiment_map[ticker],
                "timestamp": bigquery.dbapi.Timestamp.now()
            })

        # 4. THE BET: Decision logic
        target_score = sentiment_map.get(SIMULATED_TICKER, 0)
        target_price = price_map.get(SIMULATED_TICKER, 0)
        action = "IDLE"
        
        log_audit("DECISION", f"Analyzing edge for {SIMULATED_TICKER}", {"sentiment": target_score, "price": target_price})

        if target_score > 0.5:
            cost = target_price * SIMULATED_SHARES
            if current_cash >= cost:
                action = "BUY"
                current_cash -= cost
                current_holdings += SIMULATED_SHARES
                log_audit("EXECUTION", f"Executing BUY for {SIMULATED_TICKER}")
                pm.update_ledger(SIMULATED_TICKER, current_cash, current_holdings)
            else:
                log_audit("WARNING", "Insufficient capital for detected edge", {"required": cost, "available": current_cash})

        elif target_score < 0.5 and current_holdings > 0:
            action = "SELL"
            current_cash += (target_price * current_holdings)
            current_holdings = 0
            log_audit("EXECUTION", f"Executing SELL/LIQUIDATE for {SIMULATED_TICKER}")
            pm.update_ledger(SIMULATED_TICKER, current_cash, current_holdings)

        # 5. TELEMETRY
        try:
            log_watchlist_data(bq_client, f"{PROJECT_ID}.{DATASET_ID}.tickers", watchlist_rows)
            log_performance({"ticker": SIMULATED_TICKER, "action": action, "cash_remaining": current_cash, "shares": current_holdings})
        except Exception as e:
            log_audit("ERROR", f"Telemetry sync failed: {e}")

        log_audit("SHUTDOWN", "Bot cycle complete", {"final_balance": current_cash})

        return jsonify({"status": "success", "action": action, "balance": current_cash}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

