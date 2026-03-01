from google.cloud import bigquery
client = bigquery.Client(project='utopian-calling-429014-r9')
query = """
SELECT timestamp
FROM `utopian-calling-429014-r9.trading_data.watchlist_logs`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 minute)
AND gemini_reasoning is not null and gemini_reasoning != '' and gemini_reasoning != 'N/A'
ORDER BY timestamp DESC
"""
try:
    results = [r['timestamp'] for r in client.query(query).result()]
    print(f"Total calls past hour: {len(results)}")
    if len(results) > 1:
        diffs = [(results[i-1] - results[i]).total_seconds() for i in range(1, len(results))]
        print(f"Average time between calls overall: {sum(diffs)/len(diffs):.1f}s")
except Exception as e:
    print('Error:', e)
