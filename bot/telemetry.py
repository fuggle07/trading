import logging
import os
import sys
import json
from datetime import datetime
from google.cloud import bigquery

# 1. STRUCTURED LOGGING CONFIGURATION
# Cloud Run automatically picks up anything sent to stdout/stderr.
# By formatting as JSON, the Log Explorer can filter by specific fields.
class CloudLoggingFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "component": os.getenv("K_SERVICE", "trading-bot"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "module": record.module,
            "funcName": record.funcName
        }
        # Include extra dictionary data if provided via the 'extra' param
        if hasattr(record, "details"):
            log_entry["details"] = record.details
        return json.dumps(log_entry)

# Setup the master logger
logger = logging.getLogger("master-log")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(CloudLoggingFormatter())
logger.addHandler(handler)

# 2. MASTER LOGGING INTERFACE
def log_audit(event_type, message, details=None):
    """
    The primary interface for the Master Log.
    Emits a structured entry that appears in the unified stream.
    """
    # Passing 'details' in a way the formatter can pick up
    extra = {"details": details} if details else {}
    logger.info(f"[{event_type}] {message}", extra=extra)

# 3. BIGQUERY TELEMETRY (THE LEDGER AUDIT)
def log_watchlist_data(client, table_id, rows_to_insert):
    """
    Hardened BigQuery insertion for the nightly audit trail.
    """
    if not rows_to_insert:
        log_audit("TELEMETRY", "No watchlist data to log.")
        return

    # Ensure high-res timestamp format for BigQuery
    for row in rows_to_insert:
        if "timestamp" in row and isinstance(row["timestamp"], str):
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])

    try:
        errors = client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            log_audit("CRITICAL", f"BigQuery Insert Failed: {errors}")
            raise RuntimeError(f"Database out of sync: {errors}")
        
        log_audit("TELEMETRY", f"Successfully synced {len(rows_to_insert)} rows to BigQuery.")
    except Exception as e:
        log_audit("ERROR", f"Telemetry connection failure: {e}")
        raise e

def log_performance(data):
    """
    Helper to bridge legacy performance calls to the new Master Log.
    """
    log_audit("PERFORMANCE", f"Cycle complete for {data.get('ticker')}", data)

