import logging
logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, bq_client, table_id):
        self.client = bq_client
        self.table_id = table_id

    def get_state(self, ticker):
        """Fetches persistent state. Raises error if table is empty."""
        query = f"SELECT holdings, cash_balance FROM `{self.table_id}` WHERE asset_name = '{ticker}' LIMIT 1"
        results = list(self.client.query(query).result())
        
        if results:
            return {"holdings": results[0].holdings, "cash_balance": results[0].cash_balance}
        
        # High-resolution safety: No default values for real capital
        raise ValueError(f"Portfolio ledger empty for {ticker}. Initialization required.")

    def update_ledger(self, ticker, cash, holdings):
        """Updates ledger with safety logging for every state transition."""
        dml = f"""
        UPDATE `{self.table_id}`
        SET cash_balance = {cash}, holdings = {holdings}, last_updated = CURRENT_TIMESTAMP()
        WHERE asset_name = '{ticker}'
        """
        try:
            self.client.query(dml).result()
            logger.info(f"Ledger Sync: {ticker} | New Balance: ${cash:.2f}")
        except Exception as e:
            logger.critical(f"SYNC FAILURE: Database out of alignment with bot state! {e}")
            raise e

