import os
import logging
import asyncio
import httpx
from datetime import datetime
from flask import Flask, jsonify
from google.cloud import bigquery

# 1. SETUP
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
bq_client = bigquery.Client()

# 2. AUDIT CONSTANTS
HOME_LOAN_RATE = 0.052  # 5.2% Hurdle
TAX_RESERVE_RATE = 0.30 # 30% CGT Estimate for Australia
INITIAL_CAPITAL_USD = 50000.0

@app.route("/run-audit", methods=["POST"])
def run_audit():
    try:
        # A. Async Data Fetch: FX Rate & Market Context
        # We need the current AUD/USD to calculate the offset value accurately
        fx_rate = asyncio.run(get_fx_rate()) 
        
        # B. Mock: Get Current Portfolio Value from IBKR (Placeholder for actual API call)
        # In a real run, you'd use your parsed IBKR_KEY here
        current_equity_usd = 51250.0 # Example: $1,250 profit
        
        # C. TAX TELEMETRY
        total_profit_usd = current_equity_usd - INITIAL_CAPITAL_USD
        tax_buffer_usd = max(0, total_profit_usd * TAX_RESERVE_RATE)
        post_tax_equity_usd = current_equity_usd - tax_buffer_usd
        
        # D. HURDLE TELEMETRY (The "Aberfeldie Constraint")
        # How much interest would that money have saved you in the offset account?
        # daily_hurdle = (Principal * Rate) / 365
        daily_hurdle_aud = (INITIAL_CAPITAL_USD * fx_rate * HOME_LOAN_RATE) / 365
        
        # E. LOG TO BIGQUERY
        table_id = f"{os.environ.get('PROJECT_ID')}.trading_data.performance_logs"
        audit_row = {
            "timestamp": datetime.utcnow().isoformat(),
            "paper_equity": current_equity_usd,
            "tax_buffer_usd": tax_buffer_usd,
            "fx_rate_aud": fx_rate,
            "daily_hurdle_aud": daily_hurdle_aud,
            "net_alpha_usd": total_profit_usd - (tax_buffer_usd / fx_rate) # Simplified
        }
        
        # bq_client.insert_rows_json(table_id, [audit_row])
        
        return jsonify({
            "status": "audited",
            "metrics": audit_row,
            "recommendation": "HOLD" if audit_row['net_alpha_usd'] > 0 else "LIQUIDATE_TO_OFFSET"
        }), 200

    except Exception as e:
        logger.error(f"Audit engine failure: {e}")
        return jsonify({"error": str(e)}), 500

async def get_fx_rate():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.frankfurter.app/latest?from=USD&to=AUD")
        return r.json().get("rates", {}).get("AUD", 1.55)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

