import logging
import os
import sys
import json
from datetime import datetime
import pytz

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

def log_performance(client, table_id, metrics):
    """
    Logs performance metrics (Total Equity) to BigQuery.
    """
    row = {
        "timestamp": datetime.now(pytz.utc).isoformat(),
        "paper_equity": float(metrics['total_equity']),
        # We can add more fields here later as per schema
        "tax_buffer_usd": 0.0, # Placeholder
        "fx_rate_aud": 1.0, # Placeholder
        "daily_hurdle_aud": 0.0, # Placeholder
        "net_alpha_usd": 0.0, # Placeholder
        "node_id": os.getenv("K_SERVICE", "local-bot"),
        "recommendation": "HOLD", # Placeholder
    }
    
    try:
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            print(f"❌ Performance Log Error: {errors}")
        else:
            print(f"📈 Logged Performance: ${metrics['total_equity']:.2f}")
    except Exception as e:
        print(f"🔥 Performance Log Failure: {e}")

