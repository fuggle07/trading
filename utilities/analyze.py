from google.cloud import bigquery
from datetime import datetime

client = bigquery.Client()

print("=== RECENT EXECUTIONS ===")
q_exec = """
SELECT timestamp, ticker, action, quantity, price, reason, status 
FROM `utopian-calling-429014-r9.trading_data.executions`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY timestamp ASC
"""
for row in client.query(q_exec).result():
    print(
        f"[{row.timestamp}] {row.action} {row.quantity}x {row.ticker} @ ${row.price} - Status: {row.status} (Reason: {row.reason})"
    )

print("\n=== PAST 24H EQUITY ===")
q_perf = """
SELECT MIN(timestamp) as start_time, MAX(timestamp) as end_time, 
       MIN(paper_equity) as lowest, MAX(paper_equity) as highest 
FROM `utopian-calling-429014-r9.trading_data.performance_logs`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
"""
for row in client.query(q_perf).result():
    print(f"Start: {row.start_time}")
    print(f"End: {row.end_time}")
    print(f"Lowest: ${row.lowest}")
    print(f"Highest: ${row.highest}")
