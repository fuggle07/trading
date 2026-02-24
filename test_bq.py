import os
from google.cloud import bigquery

client = bigquery.Client()
PROJECT_ID = os.getenv("PROJECT_ID")

for ticker in ["ASML", "AVGO"]:
    query = f"""
    SELECT is_healthy, is_deep_healthy, deep_health_reason, metrics_json, timestamp
    FROM `{PROJECT_ID}.trading_data.fundamental_cache`
    WHERE ticker = '{ticker}'
    ORDER BY timestamp DESC
    LIMIT 5
    """
    job = client.query(query)
    print(f"--- {ticker} ---")
    for row in job:
        print(row.is_deep_healthy, row.deep_health_reason)
