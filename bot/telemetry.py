import logging
from google.cloud import bigquery
from datetime import datetime

# Configure logging for maximum visibility in Cloud Run
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_watchlist_data(client, table_id, rows_to_insert):
    """
    Hardened BigQuery insertion that fails fast on schema errors.
    """
    if not rows_to_insert:
        logger.info("Telemetry: No watchlist rows to log.")
        return

    # Ensure timestamps are actual datetime objects for BQ high-res compatibility
    for row in rows_to_insert:
        if "timestamp" in row and isinstance(row["timestamp"], str):
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])

    errors = client.insert_rows_json(table_id, rows_to_insert)

    if errors:
        # CRITICAL: If the audit trail fails, we need to know why immediately
        logger.error(f"Telemetry: BigQuery insertion failed for {table_id}: {errors}")
        raise RuntimeError(f"Database sync failed: {errors}")
    
    logger.info(f"Telemetry: Successfully logged {len(rows_to_insert)} tickers to {table_id}.")

def log_performance(data):
    """
    Standardizes performance output for Cloud Logging and future BQ ingestion.
    """
    ticker = data.get("ticker", "UNKNOWN")
    action = data.get("action", "IDLE")
    cash = data.get("cash_remaining", 0.0)
    
    # Using structured logging format for easier auditing in Cloud Run logs
    log_entry = {
        "event": "TRADE_CYCLE_COMPLETE",
        "ticker": ticker,
        "action": action,
        "shares": data.get("shares", 0),
        "final_cash": f"${cash:,.2f}",
        "status": "COMPLETED"
    }
    
    logger.info(f"AUDIT_LOG: {log_entry}")

