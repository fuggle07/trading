import logging
import os
import sys
import json
from datetime import datetime

# 1. STRUCTURED LOGGING CONFIGURATION
class CloudLoggingFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "component": os.getenv("K_SERVICE", "trading-bot"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": getattr(record, "event", "GENERIC"),
            "details": getattr(record, "details", {})
        }
        return json.dumps(log_entry)

# Setup the master logger to use stdout (Cloud Run standard)
logger = logging.getLogger("master-log")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(CloudLoggingFormatter())
logger.addHandler(handler)

# 2. MASTER LOGGING INTERFACE

def log_audit(level, message, extra=None):
    # This format is automatically parsed by Google Cloud Logging
    entry = {
        "severity": level,
        "message": message,
        "extra": extra or {}
    }
    print(json.dumps(entry))
    sys.stdout.flush() # Force the log out immediately

# 3. BIGQUERY TELEMETRY

def log_watchlist_data(client, table_id, ticker, price, sentiment=None):
    """
    Ensures the JSON keys perfectly match the BigQuery schema:
    - timestamp (TIMESTAMP)
    - ticker (STRING)
    - price (FLOAT)
    - sentiment_score (FLOAT)
    """
    row_to_insert = [
        {
            "timestamp": datetime.now(pytz.utc).isoformat(),
            "ticker": ticker,
            "price": float(price),
            "sentiment_score": float(sentiment) if sentiment else 0.0
        }
    ]

    try:
        errors = client.insert_rows_json(table_id, row_to_insert)
        if errors == []:
            print(f"✅ Telemetry: Logged {ticker} at {price}")
        else:
            print(f"❌ BQ ERROR: {errors}")
            raise RuntimeError(f"Sync failed: {errors}")
    except Exception as e:
        print(f"🔥 Critical Telemetry Failure: {e}")

def log_performance(data):
    """Standardizes cycle summary in the Master Log."""
    log_audit("PERFORMANCE", f"Cycle complete for {data.get('ticker', 'UNKNOWN')}", data)

