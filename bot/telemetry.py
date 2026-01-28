import os
import logging
from google.cloud import bigquery
from datetime import datetime, timezone

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")

def log_performance(paper_equity, fx_rate_aud, sentiment_score=None, social_volume=None):
    """Logs primary QQQ performance and sentiment to BigQuery."""
    client = bigquery.Client()
    table_id = f"{PROJECT_ID}.trading_data.performance_logs"

    rows_to_insert = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paper_equity": float(paper_equity),
            "fx_rate_aud": float(fx_rate_aud),
            "sentiment_score": float(sentiment_score) if sentiment_score is not None else None,
            "social_volume": int(social_volume) if social_volume is not None else None
        }
    ]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        logging.error(f"❌ BigQuery Performance Insert Error: {errors}")
    else:
        logging.info(f"✅ Performance Logged: ${paper_equity}")

def log_watchlist_data(ticker, price):
    """Logs individual stock prices to the watchlist_logs table."""
    client = bigquery.Client()
    table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"
    
    rows_to_insert = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "price": float(price)
        }
    ]
    
    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        # This will print directly to your Cloud Run logs
        print(f"❌ BigQuery Watchlist Insert Error for {ticker}: {errors}")
    else:
        print(f"✅ Watchlist Sync: {ticker} @ ${price}")

