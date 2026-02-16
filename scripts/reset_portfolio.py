import os
from google.cloud import bigquery

# Hardcoded for safety/simplicity in this context, or load from env
PROJECT_ID = "utopian-calling-429014-r9" 
DATASET_ID = "trading_processed"
TABLE_ID = "portfolio"

def reset_portfolio():
    print(f"⚠️  WARNING: You are about to WIPE the '{TABLE_ID}' table.")
    print(f"    Project: {PROJECT_ID}")
    print(f"    Dataset: {DATASET_ID}")
    
    # In an interactive script we'd ask for confirmation, but this is automation.
    
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    query = f"TRUNCATE TABLE `{table_ref}`"
    
    print(f"🚀 Executing: {query}")
    try:
        client.query(query).result()
        print("✅ SUCCESS: Portfolio table truncated.")
        print("👉 Next run of the bot will auto-seed $10,000 per ticker.")
    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    reset_portfolio()
