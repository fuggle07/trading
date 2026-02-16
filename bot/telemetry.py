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

def log_watchlist_data(client, table_id, rows_to_insert):
    if not rows_to_insert:
        log_audit("INFO", "No watchlist data to log.")
        return

    try:
        # We use retry to handle transient network blips
        errors = client.insert_rows_json(table_id, rows_to_insert)
        
        if errors == []:
            log_audit("INFO", f"Synced {len(rows_to_insert)} rows to BigQuery.")
        else:
            # Errors is a list of dicts: [{'index': 0, 'errors': [...]}]
            log_audit("CRITICAL", "BigQuery Insert Partial Failure", {"details": errors})
            # We raise this so the /run-audit endpoint returns a 500
            raise RuntimeError(f"BQ Sync Error: {errors}")

    except Exception as e:
        log_audit("ERROR", f"BigQuery Connection Failure: {str(e)}")
        raise e

def log_performance(data):
    """Standardizes cycle summary in the Master Log."""
    log_audit("PERFORMANCE", f"Cycle complete for {data.get('ticker', 'UNKNOWN')}", data)

