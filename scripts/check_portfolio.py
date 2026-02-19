
import os
from google.cloud import bigquery

project_id = os.getenv("PROJECT_ID", "utopian-calling-429014-r9")
client = bigquery.Client(project=project_id)
table_id = f"{project_id}.trading_data.portfolio"

print(f"Checking table: {table_id}")

try:
    query = f"SELECT * FROM `{table_id}`"
    results = client.query(query).result()
    
    print(f"{'Asset':<10} | {'Holdings':<10} | {'Cash':<15} | {'Avg Price':<10} | {'Last Updated'}")
    print("-" * 70)
    for row in results:
        cash = row.cash_balance if row.cash_balance is not None else 0.0
        holdings = row.holdings if row.holdings is not None else 0.0
        avg = row.avg_price if row.avg_price is not None else 0.0
        print(f"{row.asset_name:<10} | {holdings:<10.4f} | ${cash:<14.2f} | ${avg:<9.2f} | {row.last_updated}")

except Exception as e:
    print(f"Error: {e}")
