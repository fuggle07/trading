from google.cloud import bigquery
from datetime import datetime
import pandas as pd

client = bigquery.Client(project='utopian-calling-429014-r9')

print("=== RECENT EXECUTIONS ===")
q_exec = """
SELECT timestamp, asset_name, action, quantity, price, value, reason 
FROM `utopian-calling-429014-r9.trading_data.executions`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY timestamp ASC
"""
df_exec = client.query(q_exec).to_dataframe()
print(df_exec)

print("\n=== RECENT SIGNALS ===")
q_sig = """
SELECT timestamp, ticker, signal, reason, confidence 
FROM `utopian-calling-429014-r9.trading_data.trade_signals_log`
WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND signal != 'HOLD'
ORDER BY timestamp ASC
"""
df_sig = client.query(q_sig).to_dataframe()
print(df_sig)
