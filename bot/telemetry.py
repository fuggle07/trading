import logging
from google.cloud import bigquery

# Configure logging to ensure visibility in Cloud Run
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_watchlist_data(client, table_id, rows_to_insert):
    """
    Inserts rows into BigQuery with explicit error checking.
    """
    if not rows_to_insert:
        logger.warning("Telemetry: No tickers provided for insertion.")
        return True

    logger.info(f"Telemetry: Attempting to insert {len(rows_to_insert)} rows into {table_id}")
    
    # insert_rows_json returns a list of error dictionaries
    errors = client.insert_rows_json(table_id, rows_to_insert)
    
    if errors == []:
        logger.info("Telemetry: Watchlist logged successfully to BigQuery.")
        return True
    else:
        # High-resolution error reporting
        for error in errors:
            logger.error(f"Telemetry: BigQuery insertion error in row {error.get('index')}: {error.get('errors')}")
        return False

