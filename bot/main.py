import os
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from flask import Flask, jsonify
from google.cloud import bigquery
from ib_async import IB, util

# 1. SURGICAL FIX: Use absolute import for Cloud Run entry point
from telemetry import log_performance

# SETUP & LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Initialize BigQuery Client
bq_client = bigquery.Client()

# CONFIGURATION (Hurdle: 5.2% Offset Account)
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")
HOME_LOAN_RATE = 0.052  
TAX_RESERVE_RATE = 0.30 
INITIAL_CAPITAL_USD = 50000.0

async def fetch_ibkr_equity():
    """
    Actuator: Connects to IBKR TWS/Gateway to fetch Net Liquidation Value.
    """
    ib = IB()
    try:
        # Connect to your local gateway or the specified host
        # Default port for TWS Paper is 7497, Gateway Paper is 4002
        await ib.connectAsync('127.0.0.1', 4002, clientId=1)
        
        # Fetch account summary
        summary = await ib.accountSummaryAsync()
        
        # Surgical extraction of Net Liquidation Value (Total Equity)
        net_liq = next((item.value for item in summary if item.tag == 'NetLiquidation'), 50000.0)
        
        await ib.disconnectAsync()
        return float(net_liq)
    except Exception as e:
        logger.error(f"IBKR Actuator Failure: {e}")
        return 50000.0  # Safe fallback to prevent audit crash

@app.route("/")
def health_check():
    """Cloud Run lifecycle management signal."""
    return "Aberfeldie Trading Node: Operational", 200

@app.route("/run-audit", methods=["POST"])
def run_audit():
    try:
        # A. Context Fetching (Concurrent FX Poll for AUD/USD)
        fx_rate = asyncio.run(get_fx_rate())
        
        # B. Trading Logic Placeholder (Mock Equity for Audit)
        current_equity_usd = 51250.0 
        
        # C. Hurdle & Tax Telemetry Calculations
        total_profit_usd = current_equity_usd - INITIAL_CAPITAL_USD
        tax_buffer_usd = max(0, total_profit_usd * TAX_RESERVE_RATE)
        daily_hurdle_aud = (INITIAL_CAPITAL_USD * fx_rate * HOME_LOAN_RATE) / 365
        
        # Calculation for Net Alpha (USD comparison)
        # (Post-Tax Profit) - (Daily Hurdle converted back to USD)
        net_alpha_usd = (total_profit_usd - tax_buffer_usd) - (daily_hurdle_aud / fx_rate)
        
        # D. Data Silo Injection
        table_id = f"{PROJECT_ID}.trading_data.performance_logs"
        audit_row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paper_equity": float(current_equity_usd),
            "tax_buffer_usd": float(tax_buffer_usd),
            "fx_rate_aud": float(fx_rate),
            "daily_hurdle_aud": float(daily_hurdle_aud),
            "net_alpha_usd": float(net_alpha_usd),
            "node_id": "aberfeldie-01",
            "recommendation": "HOLD" if net_alpha_usd > 0 else "LIQUIDATE_TO_OFFSET"
        }
        
        # SURGICAL FIX: Re-enabled BigQuery actuation
        errors = bq_client.insert_rows_json(table_id, [audit_row])
        
        if errors:
            logger.error(f"BigQuery Insert Error: {errors}")
            return jsonify({"status": "error", "message": "BigQuery insertion failed"}), 500

        logger.info(f"Audit Successful: Net Alpha ${net_alpha_usd:.2f} USD")
        return jsonify({"status": "success", "metrics": audit_row}), 200

    except Exception as e:
        logger.error(f"Audit engine failure: {e}")
        return jsonify({"error": str(e)}), 500

async def get_fx_rate():
    """Fetch current spot FX for accurate offset hurdle math."""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("https://api.frankfurter.app/latest?from=USD&to=AUD", timeout=5.0)
            return r.json().get("rates", {}).get("AUD", 1.55)
        except Exception as e:
            logger.warning(f"FX Fetch failed, using fallback: {e}")
            return 1.55 # Safe Australian Fallback

if __name__ == "__main__":
    # Required binding for Cloud Run environment
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

