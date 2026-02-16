
import logging
import os
import json
from google.cloud import bigquery
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger("execution-manager")

class ExecutionManager:
    """
    Handles order execution and logs trades to BigQuery.
    """
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID")
        self.bq_client = None
        self.table_id = "trading_data.executions" # Assumed table based on convention
        
        if self.project_id:
            try:
                self.bq_client = bigquery.Client(project=self.project_id)
                logger.info(f"ExecutionManager connected to BigQuery project: {self.project_id}")
            except Exception as e:
                logger.error(f"Failed to initialize BigQuery client: {e}")
        else:
            logger.warning("PROJECT_ID not found. BigQuery logging disabled.")

    def place_order(self, signal: dict) -> dict:
        """
        Executes an order based on the signal and logs it.
        In this simulated environment, it just logs and returns a success message.
        """
        ticker = signal.get("ticker", "UNKNOWN")
        action = signal.get("action", "HOLD")
        reason = signal.get("reason", "No reason provided")
        price = signal.get("price", 0.0)
        
        logger.info(f"EXECUTING {action} on {ticker} @ {price} | Reason: {reason}")
        
        # 1. Execute Order (Simulated)
        # In a real system, this would call IBKR or an exchange API
        execution_id = f"sim-exec-{int(datetime.now().timestamp())}"
        
        # 2. Log to BigQuery
        execution_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution_id,
            "ticker": ticker,
            "action": action,
            "price": float(price),
            "quantity": 1, # Default to 1 for simulation
            "reason": reason,
            "status": "FILLED"
        }
        
        self._log_to_bigquery(execution_data)
        
        return {
            "status": "FILLED",
            "execution_id": execution_id,
            "details": execution_data
        }

    def _log_to_bigquery(self, data: dict):
        """
        Logs execution data to BigQuery. Gracefully handles missing tables.
        """
        if not self.bq_client:
            logger.debug("Skipping BQ log (No Client)")
            return

        try:
            # Defensive check
            if self.bq_client is None:
                logger.warning("BigQuery client is None (unexpected), skipping log.")
                return

            # Insert rows returns a list of errors if any
            errors = self.bq_client.insert_rows_json(self.table_id, [data])
            if errors:
                logger.error(f"BigQuery Insert Errors: {errors}")
            else:
                logger.info(f"Logged execution {data['execution_id']} to {self.table_id}")
                
        except Exception as e:
            # Catch-all for API errors (e.g., 404 Not Found if table doesn't exist)
            logger.warning(f"Failed to log to BigQuery ({self.table_id}): {e}")