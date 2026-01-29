import logging

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, bq_client, table_id):
        """
        Initializes with a BigQuery client and the fully qualified table name.
        """
        self.client = bq_client
        self.table_id = table_id

    def get_state(self, ticker):
        """
        Fetches current holdings and cash for a specific ticker.
        Raises ValueError if no data is found (table not seeded).
        """
        query = f"SELECT holdings, cash_balance FROM `{self.table_id}` WHERE asset_name = '{ticker}' LIMIT 1"
        query_job = self.client.query(query)
        results = list(query_job.result())
        
        if results:
            return {
                "holdings": results[0].holdings,
                "cash_balance": results[0].cash_balance
            }
        
        # High-resolution safety: Don't guess. If the row is missing, the system is misconfigured.
        raise ValueError(f"No portfolio data found for {ticker} in {self.table_id}. Run Terraform seed job.")

    def update_ledger(self, ticker, cash, holdings):
        """
        Updates the BigQuery table with new cash and holdings.
        """
        dml = f"""
        UPDATE `{self.table_id}`
        SET cash_balance = {cash}, 
            holdings = {holdings}, 
            last_updated = CURRENT_TIMESTAMP()
        WHERE asset_name = '{ticker}'
        """
        try:
            self.client.query(dml).result()
            logger.info(f"Ledger Updated | {ticker} | Cash: ${cash:.2f} | Shares: {holdings}")
        except Exception as e:
            logger.critical(f"CRITICAL: Ledger update failed: {e}. State is now inconsistent!")
            raise e

