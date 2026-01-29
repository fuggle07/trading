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
def log_audit(event_type, message, details=None):
    """
    The primary interface for the Master Log.
    Emits a structured entry tagged with an event type.
    """
    # Create a log record with extra attributes for the formatter
    extra = {"event": event_type, "details": details or {}}
    logger.info(message, extra=extra)

# 3. BIGQUERY TELEMETRY
def log_watchlist_data(client, table_id, rows_to_insert):
    """Logs watchlist data to BQ and records status in the Master Log."""
    if not rows_to_insert:
        log_audit("TELEMETRY", "No watchlist data to log.")
        return

    try:
        errors = client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            log_audit("CRITICAL", f"BigQuery Insert Failed", {"errors": errors})
            raise RuntimeError(f"Database sync failed: {errors}")
        
        log_audit("TELEMETRY", f"Successfully synced {len(rows_to_insert)} rows.")
    except Exception as e:
        log_audit("ERROR", f"Telemetry connection failure: {e}")
        raise e

def log_performance(data):
    """Standardizes cycle summary in the Master Log."""
    log_audit("PERFORMANCE", f"Cycle complete for {data.get('ticker', 'UNKNOWN')}", data)

