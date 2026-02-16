import logging
import os
import json
from google.cloud import bigquery
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger("execution-manager")

class ExecutionManager:
    """
    Handles order execution, validation against portfolio, and logging.
    """
    def __init__(self, portfolio_manager=None):
        self.project_id = os.getenv("PROJECT_ID")
        self.bq_client = None
        self.table_id = "trading_data.executions"
        self.portfolio_manager = portfolio_manager
        
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
        Executes an order if funds/holdings allow, then logs it.
        """
        ticker = signal.get("ticker", "UNKNOWN")
        action = signal.get("action", "HOLD")
        reason = signal.get("reason", "No reason provided")
        price = float(signal.get("price", 0.0))
        quantity = 1 # Default to 1 share for now
        
        logger.info(f"PROCESSING {action} on {ticker} @ {price} | Reason: {reason}")
        
        # 0. Portfolio Validation (The Gatekeeper)
        if self.portfolio_manager:
            try:
                # Get current state (or init if empty)
                try:
                    state = self.portfolio_manager.get_state(ticker)
                except ValueError:
                    # Initialize if not found (First time trading this ticker)
                    state = {"holdings": 0.0, "cash_balance": 10000.0} # $10k seed execution
                    logger.info(f"Initializing portfolio for {ticker} with $10,000 simulated cash.")

                cash = state['cash_balance']
                holdings = state['holdings']
                
                # Check constraints
                if action == "BUY":
                    cost = price * quantity
                    if cash < cost:
                        logger.warning(f"❌ REJECTED: Insufficient funds (${cash:.2f} < ${cost:.2f})")
                        return {"status": "REJECTED", "reason": "INSUFFICIENT_FUNDS"}
                    
                    # Update State (Simulated Settlement)
                    new_cash = cash - cost
                    new_holdings = holdings + quantity
                    self.portfolio_manager.update_ledger(ticker, new_cash, new_holdings)
                    
                elif action == "SELL":
                    if holdings < quantity:
                         logger.warning(f"❌ REJECTED: Insufficient holdings ({holdings} < {quantity})")
                         return {"status": "REJECTED", "reason": "INSUFFICIENT_HOLDINGS"}
                    
                    # Update State
                    new_cash = cash + (price * quantity)
                    new_holdings = holdings - quantity
                    self.portfolio_manager.update_ledger(ticker, new_cash, new_holdings)
                    
            except Exception as e:
                logger.error(f"Portfolio Validation Failed: {e}")
                return {"status": "ERROR", "reason": str(e)}
        else:
             logger.warning("⚠️ PortfolioManager not connected! executing blindly (Sim Mode)")

        # 1. Execute Log
        execution_id = f"exec-{int(datetime.now().timestamp())}-{ticker}"
        
        execution_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": execution_id,
            "ticker": ticker,
            "action": action,
            "price": price,
            "quantity": quantity,
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
        """Logs execution data to BigQuery."""
        if not self.bq_client:
            return

        try:
            errors = self.bq_client.insert_rows_json(self.table_id, [data])
            if errors:
                logger.error(f"BigQuery Insert Errors: {errors}")
            else:
                logger.info(f"Logged execution {data['execution_id']} to {self.table_id}")
        except Exception as e:
            logger.warning(f"Failed to log to BigQuery ({self.table_id}): {e}")