# bot/telemetry.py
import os
import logging
from google.cloud import bigquery
from datetime import datetime, timezone

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")
DATASET_ID = "trading_data"
TABLE_ID = "performance_logs"

# Constants for the Aberfeldie Node
HOME_LOAN_RATE = 0.052  # 5.2% Hurdle
TAX_RESERVE_RATE = 0.30 # 30% CGT Reserve
INITIAL_CAPITAL_USD = 50000.0

client = bigquery.Client()

def log_performance(paper_equity, fx_rate_aud):
    """
    Surgically calculates tax and hurdle metrics before logging to BigQuery.
    """
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # 1. Tax Telemetry (30% on Profit)
    profit_usd = max(0, paper_equity - INITIAL_CAPITAL_USD)
    tax_buffer_usd = profit_usd * TAX_RESERVE_RATE
    
    # 2. Hurdle Telemetry (Daily interest cost of $50k loan)
    # Conversion to AUD is required for offset account comparison
    daily_hurdle_aud = (INITIAL_CAPITAL_USD * fx_rate_aud * HOME_LOAN_RATE) / 365
    
    # 3. Net Alpha (USD)
    # (Total Equity - Initial Capital - Tax) - (Daily Hurdle converted to USD)
    net_alpha_usd = (profit_usd - tax_buffer_usd) - (daily_hurdle_aud / fx_rate_aud)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "tax_buffer_usd": float(tax_buffer_usd),
        "fx_rate_aud": float(fx_rate_aud),
        "daily_hurdle_aud": float(daily_hurdle_aud),
        "net_alpha_usd": float(net_alpha_usd),
        "node_id": "aberfeldie-01",
        "recommendation": "HOLD" if net_alpha_usd > 0 else "LIQUIDATE_TO_OFFSET"
    }

    try:
        errors = client.insert_rows_json(table_ref, [row])
        if errors:
            logging.error(f"BigQuery Insert Errors: {errors}")
        else:
            logging.info(f"Audit Logged: Net Alpha ${net_alpha_usd:.2f} USD")
        return row
    except Exception as e:
        logging.error(f"Telemetry Failed: {e}")
        return None

