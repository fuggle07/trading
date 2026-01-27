# bot/telemetry.py - v3.2 Hurdle-Aware
import os
from google.cloud import bigquery
from datetime import datetime, timezone

client = bigquery.Client()

def log_performance(paper_equity, index_price, fx_rate_aud, capital_usd, hurdle_rate):
    """
    Calculates opportunity cost against the mortgage offset.
    """
    project_id = os.getenv("PROJECT_ID")
    table_id = f"{project_id}.trading_data.performance_logs"

    # Calculate daily hurdle: (Capital in AUD * Rate) / 365
    daily_hurdle_aud = (capital_usd * fx_rate_aud * hurdle_rate) / 365

    rows_to_insert = [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "index_price": float(index_price),
        "fx_rate_aud": float(fx_rate_aud),
        "opportunity_cost_aud": float(daily_hurdle_aud),
        "node_id": "Aberfeldie-PRO-01"
    }]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        print(f"❌ [HURDLE TELEMETRY ERROR]: {errors}")
