from google.cloud import bigquery
import os

PROJECT_ID = os.getenv("PROJECT_ID", "utopian-calling-429014-r9")
TABLE_ID = "trading_data.portfolio"

def reset_cash():
    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    UPDATE `{PROJECT_ID}.{TABLE_ID}`
    SET cash_balance = 100000.0,
    last_updated = CURRENT_TIMESTAMP()
    WHERE asset_name = 'USD'
    """

    print(f"🚀 Resetting Cash in {TABLE_ID} to $100,000...")
    try:
        query_job = client.query(query)
        query_job.result()
        print("✅ Cash reset successfully.")
    except Exception as e:
        print(f"❌ Failed to reset cash: {e}")

if __name__ == "__main__":
    reset_cash()
