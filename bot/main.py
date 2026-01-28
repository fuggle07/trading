# bot/main.py
import os
import logging
import asyncio
import httpx
from datetime import datetime
from flask import Flask, jsonify
from google.cloud import bigquery

# SETUP
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__) # This 'app' object is the entry point for Gunicorn
bq_client = bigquery.Client()

# AUDIT CONSTANTS (Hurdle: 5.2% Offset Account)
HOME_LOAN_RATE = 0.052  
TAX_RESERVE_RATE = 0.30 
INITIAL_CAPITAL_USD = 50000.0

@app.route("/")
def health_check():
    """Health check for Cloud Run lifecycle management."""
    return "Aberfeldie Trading Node: Operational", 200

@app.route("/run-audit", methods=["POST"])
def run_audit():
    try:
        # A. Async Context Fetching
        fx_rate = asyncio.run(get_fx_rate()) 
        
        # B. Trading Logic Placeholder
        current_equity_usd = 51250.0 
        
        # C. Hurdle & Tax Telemetry
        total_profit_usd = current_equity_usd - INITIAL_CAPITAL_USD
        tax_buffer_usd = max(0, total_profit_usd * TAX_RESERVE_RATE)
        daily_hurdle_aud = (INITIAL_CAPITAL_USD * fx_rate * HOME_LOAN_RATE) / 365
        
        # D. Data Silo Injection
        table_id = f"{os.environ.get('PROJECT_ID')}.trading_data.performance_logs"
        audit_row = {
            "timestamp": datetime.utcnow().isoformat(),
            "paper_equity": current_equity_usd,
            "tax_buffer_usd": tax_buffer_usd,
            "fx_rate_aud": fx_rate,
            "daily_hurdle_aud": daily_hurdle_aud,
            "net_alpha_usd": total_profit_usd - (tax_buffer_usd / fx_rate)
        }
        
        # bq_client.insert_rows_json(table_id, [audit_row])
        
        return jsonify({"status": "success", "metrics": audit_row}), 200

    except Exception as e:
        logger.error(f"Audit engine failure: {e}")
        return jsonify({"error": str(e)}), 500

async def get_fx_rate():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.frankfurter.app/latest?from=USD&to=AUD")
        return r.json().get("rates", {}).get("AUD", 1.55)

if __name__ == "__main__":
    # Binding to 0.0.0.0 is mandatory for Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

