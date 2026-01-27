import os
from google.cloud import bigquery
from datetime import datetime, timezone

# Client persistence: Initialized once at the module level to reduce latency
client = bigquery.Client()

def log_performance(paper_equity, index_price):
    """Pushes data to BigQuery using a persistent client."""
    project_id = os.getenv("PROJECT_ID")
    table_id = f"{project_id}.trading_data.performance_logs"

    rows_to_insert = [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "index_price": float(index_price),
        "node_id": "Aberfeldie-PRO-01"
    }]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        print(f"❌ [TELEMETRY ERROR]: {errors}")

