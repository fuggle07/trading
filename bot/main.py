import os
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from flask import Flask, jsonify
from google.cloud import bigquery
from ib_async import IB

# SURGICAL FIX: Absolute import for container entry point
from telemetry import log_performance

# SETUP & LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Initialize BigQuery Client
bq_client = bigquery.Client()

# CONFIGURATION (The Aberfeldie Constraint)
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")
HOME_LOAN_RATE = 0.052  # 5.2% Mortgage Hurdle
TAX_RESERVE_RATE = 0.30 # 30% Australian CGT
INITIAL_CAPITAL_USD = 50000.0

@app.route("/")
def health_check():
    """Cloud Run lifecycle management signal."""
    return "Aberfeldie Trading Node: Operational", 200

@app.route("/run-audit", methods=["POST"])
def run_audit():
    try:
        # 1. Concurrent Context Gathering (FX and IBKR Equity)
        # Managed via internal event loop for Flask compatibility
        fx_rate, current_equity_usd = asyncio.run(gather_audit_context())
        
        # 2. Hurdle & Tax Telemetry Calculations
        total_profit_usd = current_equity_usd - INITIAL_CAPITAL_USD
        tax_buffer_usd = max(0, total_profit_usd * TAX_RESERVE_RATE)
        
        # Calculate daily mortgage cost in AUD
        daily_hurdle_aud = (INITIAL_CAPITAL_USD * fx_rate * HOME_LOAN_RATE) / 365
        
        # Calculation for Net Alpha (USD comparison)
        # (Post-Tax Profit) - (Daily Hurdle converted to USD)
        net_alpha_usd = (total_profit_usd - tax_buffer_usd) - (daily_hurdle_aud / fx_rate)
        
        # 3. Data Silo Injection Payload
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
        
        # 4. BIGQUERY ACTUATION: Write heartbeat to cloud storage
        errors = bq_client.insert_rows_json(table_id, [audit_row])
        
        if errors:
            logger.error(f"BigQuery Insert Error: {errors}")
            return jsonify({"status": "error", "message": "BigQuery insertion failed"}), 500

        logger.info(f"Audit Successful: Net Alpha ${net_alpha_usd:.2f} USD")
        return jsonify({"status": "success", "metrics": audit_row}), 200

    except Exception as e:
        logger.error(f"Audit engine failure: {e}")
        return jsonify({"error": str(e)}), 500

async def gather_audit_context():
    """Polls external sensors concurrently."""
    return await asyncio.gather(get_fx_rate(), fetch_ibkr_equity())

async def get_fx_rate():
    """Fetch current spot FX for accurate offset hurdle math."""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("https://api.frankfurter.app/latest?from=USD&to=AUD", timeout=5.0)
            return r.json().get("rates", {}).get("AUD", 1.55)
        except Exception as e:
            logger.warning(f"FX Fetch failed, using fallback: {e}")
            return 1.55 # Safe Australian Fallback

async def fetch_ibkr_equity():
    """Actuator: Probes IBKR Net Liquidation Value."""
    ib = IB()
    try:
        # Assumes IBKR Gateway is reachable at this address
        await ib.connectAsync('127.0.0.1', 4002, clientId=1)
        summary = await ib.accountSummaryAsync()
        net_liq = next((item.value for item in summary if item.tag == 'NetLiquidation'), 50000.0)
        await ib.disconnectAsync()
        return float(net_liq)
    except Exception as e:
        logger.warning(f"IBKR sensor failed, using capital base: {e}")
        return INITIAL_CAPITAL_USD

if __name__ == "__main__":
    # Required binding for Cloud Run environment
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

