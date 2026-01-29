import logging

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, bq_client, table_id):
        self.client = bq_client
        self.table_id = table_id

    def get_state(self, ticker):
        """Fetches current holdings and cash from the persistent BQ table."""
        query = f"SELECT holdings, cash_balance FROM `{self.table_id}` WHERE asset_name = '{ticker}' LIMIT 1"
        results = list(self.client.query(query).result())
        if results:
            return results[0]
        # Initial state fallback
        return {"holdings": 0.0, "cash_balance": 50000.0}

    def update_ledger(self, ticker, cash, holdings):
        """Executes a DML update to the BQ portfolio table."""
        dml = f"""
        UPDATE `{self.table_id}`
        SET cash_balance = {cash}, 
            holdings = {holdings}, 
            last_updated = CURRENT_TIMESTAMP()
        WHERE asset_name = '{ticker}'
        """
        self.client.query(dml).result()
        logger.info(f"DB Sync Successful | Asset: {ticker} | New Cash: ${cash:.2f}")

