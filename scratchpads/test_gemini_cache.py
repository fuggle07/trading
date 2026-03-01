from google.cloud import bigquery
import os, datetime

client = bigquery.Client()
query = """
SELECT count(*) as req_count
FROM `utopian-calling-429014-r9.trading_data.log_table`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE)
AND gemini_reasoning IS NOT NULL AND gemini_reasoning != 'N/A' AND gemini_reasoning != ''
"""
try:
    results = list(client.query(query).result())
    print(f"Watchlist activity: {results[0]['req_count']} Gemini calls in the last hour")
except Exception as e:
    print(f"Error: {e}")
