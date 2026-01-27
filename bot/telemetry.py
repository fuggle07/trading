# bot/telemetry.py - Performance Logging Service
import os
from google.cloud import bigquery
from datetime import datetime, timezone

def log_performance(paper_equity, index_price):
    """
    Surgically pushes performance data to BigQuery.
    Ensures zero-latency impact on the main audit loop.
    """
    client = bigquery.Client()
    project_id = os.getenv("PROJECT_ID")
    table_id = f"{project_id}.trading_data.performance_logs"

    # Construct the data payload
    rows_to_insert = [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "index_price": float(index_price),
        "node_id": "Aberfeldie-01"
    }]

    # Streaming insert for real-time dashboard updates
    errors = client.insert_rows_json(table_id, rows_to_insert)
    
    if not errors:
        print(f"📊 [TELEMETRY] Performance Synced: ${paper_equity} vs Index ${index_price}")
    else:
        print(f"❌ [TELEMETRY] Critical Failure: {errors}")

