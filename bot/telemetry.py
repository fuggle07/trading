# bot/telemetry.py - Performance Logging Service
import os
from google.cloud import bigquery
from datetime import datetime, timezone

def log_performance(paper_equity, index_price):
    """Surgically pushes performance data to BigQuery."""
    client = bigquery.Client()
    project_id = os.getenv("PROJECT_ID")
    table_id = f"{project_id}.trading_data.performance_logs"

    rows_to_insert = [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "index_price": float(index_price),
        "node_id": "Aberfeldie-Node-01"
    }]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if not errors:
        print(f"📊 [TELEMETRY] Performance synced: ${paper_equity} vs Index ${index_price}")
    else:
        print(f"❌ [TELEMETRY] Failed to sync: {errors}")

