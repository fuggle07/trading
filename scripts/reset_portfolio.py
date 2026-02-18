from google.cloud import bigquery

# Hardcoded for safety/simplicity in this context, or load from env
PROJECT_ID = "utopian-calling-429014-r9"
DATASET_ID = "trading_data" # Corrected from 'trading_processed'
TABLE_ID = "portfolio"

def reset_portfolio():
    print(f"⚠️ WARNING: You are about to WIPE the '{TABLE_ID}' table.")
    print(f" Project: {PROJECT_ID}")
    print(f" Dataset: {DATASET_ID}")

    # In an interactive script we'd ask for confirmation, but this is automation.

    # Explicitly set location for US-Central1 dataset (as per Terraform)
    client = bigquery.Client(project=PROJECT_ID, location="us-central1")
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    query = f"TRUNCATE TABLE `{table_ref}`"

    print(f"🚀 Executing: {query} [Location: us-central1]")
    try:
        # Pass location explicitly to query job as well
        client.query(query, location="us-central1").result()
        print("✅ SUCCESS: Portfolio table truncated.")

        # New: Seed the Global Cash Pool
        seed_query = f"""
        INSERT INTO `{table_ref}` (asset_name, holdings, cash_balance, avg_price, last_updated)
        VALUES ('USD', 0.0, 50000.0, 0.0, CURRENT_TIMESTAMP())
        """
        print("🌱 Seeding Global Cash Pool (USD) with $50,000...")
        client.query(seed_query, location="us-central1").result()

        print("✅ SUCCESS: Global Cash Pool Initialized.")
    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    reset_portfolio()
