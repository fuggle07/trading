# bot/telemetry.py - v3.1 Tax-Aware Optimized
import os
from google.cloud import bigquery
from datetime import datetime, timezone

client = bigquery.Client()

def log_performance(paper_equity, index_price, fx_rate_aud=1.52, brokerage=0.0):
    """
    Pushes tax-aware data to BigQuery.
    fx_rate_aud: The conversion rate to AUD (e.g., 1.52).
    brokerage: The fee paid for the transaction in USD.
    """
    project_id = os.getenv("PROJECT_ID")
    table_id = f"{project_id}.trading_data.performance_logs"

    rows_to_insert = [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "index_price": float(index_price),
        "fx_rate_aud": float(fx_rate_aud),
        "brokerage_fees_usd": float(brokerage),
        "node_id": "Aberfeldie-PRO-01"
    }]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        print(f"❌ [TAX TELEMETRY ERROR]: {errors}")

