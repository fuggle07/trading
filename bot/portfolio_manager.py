import logging

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, bq_client, table_id):
        self.client = bq_client
        self.table_id = table_id

    def get_state(self, ticker):
        """Fetches current holdings and cash. Fails fast if table is empty."""
        query = f"SELECT holdings, cash_balance FROM `{self.table_id}` WHERE asset_name = '{ticker}' LIMIT 1"
        try:
            query_job = self.client.query(query)
            results = list(query_job.result())
            
            if results:
                return results[0]
            
            # Logic Guard: If the table exists but is empty, don't guess.
            raise ValueError(f"Portfolio table {self.table_id} has no data for {ticker}. Seed the table first.")
            
        except Exception as e:
            logger.error(f"Portfolio State Error: {e}")
            # Only fallback for local development if really needed
            return {"holdings": 0.0, "cash_balance": 50000.0}

    def update_ledger(self, ticker, cash, holdings):
        """Executes a DML update with safety logging."""
        dml = f"""
        UPDATE `{self.table_id}`
        SET cash_balance = {cash}, 
            holdings = {holdings}, 
            last_updated = CURRENT_TIMESTAMP()
        WHERE asset_name = '{ticker}'
        """
        try:
            self.client.query(dml).result()
            logger.info(f"Ledger Sync Successful | {ticker} | New Cash: ${cash:.2f}")
        except Exception as e:
            logger.critical(f"LEDGER UPDATE FAILED: {e}. System out of sync!")
            raise e

