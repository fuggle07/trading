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

    def place_order(self, ticker, action, quantity, price, cash_available=0.0):
        """
        Executes an order if funds/holdings allow, then logs it.
        Now supports Unified Cash Pool via 'cash_available' parameter.
        """
        reason = "Strategy Signal" # Simple default
        
        logger.info(f"PROCESSING {action} on {ticker} @ {price} | Cash Alloc: ${cash_available:.2f}")
        
        # 0. Portfolio Validation (The Gatekeeper)
        if self.portfolio_manager:
            try:
                # Get current holdings state for this TICKER
                # Note: We don't check cash here anymore, we check 'cash_available' passed in
                try:
                    state = self.portfolio_manager.get_state(ticker)
                except ValueError:
                    state = {"holdings": 0.0, "avg_price": 0.0}

                holdings = state['holdings']
                
                # Check constraints
                if action == "BUY":
                    # Calculate max quantity based on allocated cash
                    if quantity == 0:
                        # Auto-calculate max shares
                        quantity = int(cash_available // price)
                    
                    cost = price * quantity
                    
                    if quantity <= 0:
                        logger.warning(f"❌ REJECTED: Quantity would be 0 (Cash ${cash_available:.2f} / Price ${price:.2f})")
                        return {"status": "REJECTED", "reason": "ZERO_QUANTITY"}

                    if cash_available < cost:
                        logger.warning(f"❌ REJECTED: Insufficient funds (${cash_available:.2f} < ${cost:.2f})")
                        return {"status": "REJECTED", "reason": "INSUFFICIENT_FUNDS"}
                    
                    # Update State (Simulated Settlement)
                    # For Unified Cash: We pass the NEGATIVE cost as cash_delta
                    self.portfolio_manager.update_ledger(ticker, -cost, quantity, price, action="BUY")
                    
                elif action == "SELL":
                    if quantity == 0:
                        # Auto-sell ALL
                        quantity = holdings
                        
                    if holdings < quantity or quantity <= 0:
                         logger.warning(f"❌ REJECTED: Insufficient holdings ({holdings} < {quantity})")
                         return {"status": "REJECTED", "reason": "INSUFFICIENT_HOLDINGS"}
                    
                    # Update State
                    # For Unified Cash: We pass the POSITIVE revenue as cash_delta
                    revenue = price * quantity
                    self.portfolio_manager.update_ledger(ticker, revenue, -quantity, price, action="SELL")
                    
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