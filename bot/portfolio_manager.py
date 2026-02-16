import logging
logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, bq_client, table_id):
        self.client = bq_client
        self.table_id = table_id

    def get_state(self, ticker):
        """Fetches persistent state. Raises error if table is empty."""
        query = f"SELECT holdings, cash_balance, avg_price FROM `{self.table_id}` WHERE asset_name = '{ticker}' LIMIT 1"
        results = list(self.client.query(query).result())
        
        if results:
            # Handle existing rows that might have NULL avg_price
            avg_price = results[0].avg_price if results[0].avg_price is not None else 0.0
            return {
                "holdings": results[0].holdings,
                "cash_balance": results[0].cash_balance,
                "avg_price": avg_price
            }
        
        # High-resolution safety: No default values for real capital
        raise ValueError(f"Portfolio ledger empty for {ticker}. Initialization required.")

    def ensure_portfolio_state(self, ticker):
        """
        Seeds the portfolio for a new ticker if it doesn't exist.
        Default: $10,000 Paper Cash, 0 Holdings.
        """
        try:
            # Check if exists
            query = f"SELECT asset_name FROM `{self.table_id}` WHERE asset_name = '{ticker}'"
            results = list(self.client.query(query).result())
            
            if not results:
                logger.info(f"🌱 Seeding portfolio for {ticker} with $10,000")
                initial_cash = 10000.0
                initial_holdings = 0.0
                initial_avg_price = 0.0
                
                dml = f"""
                INSERT INTO `{self.table_id}` (asset_name, holdings, cash_balance, avg_price, last_updated)
                VALUES ('{ticker}', {initial_holdings}, {initial_cash}, {initial_avg_price}, CURRENT_TIMESTAMP())
                """
                self.client.query(dml).result()
                
        except Exception as e:
            logger.error(f"Failed to ensure portfolio state for {ticker}: {e}")

    def update_ledger(self, ticker, cash, holdings, price=None, action=None):
        """
        Updates ledger and recalculates Weighted Average Cost Basis.
        """
        # 1. Get current state to calculate WAC
        try:
            current_state = self.get_state(ticker)
            old_holdings = current_state['holdings']
            old_avg = current_state['avg_price']
        except:
            # If fetch fails, assume 0 (Should not happen if seeded)
            old_holdings = 0.0
            old_avg = 0.0

        # 2. Calculate New Average Price
        new_avg = old_avg # Default: No change (e.g. for Sells)
        
        if action == "BUY" and price is not None and holdings > 0:
            # Weighted Average Cost Formula
            # NewAvg = ((OldShares * OldAvg) + (NewShares * BuyPrice)) / TotalShares
            new_shares = holdings - old_holdings
            if new_shares > 0:
                total_cost = (old_holdings * old_avg) + (new_shares * price)
                new_avg = total_cost / holdings
        
        # If Holdings go to 0, reset avg to 0
        if holdings == 0:
            new_avg = 0.0

        dml = f"""
        UPDATE `{self.table_id}`
        SET cash_balance = {cash}, 
            holdings = {holdings}, 
            avg_price = {new_avg},
            last_updated = CURRENT_TIMESTAMP()
        WHERE asset_name = '{ticker}'
        """
        try:
            self.client.query(dml).result()
            logger.info(f"Ledger Sync: {ticker} | New Balance: ${cash:.2f} | Avg Cost: ${new_avg:.2f}")
        except Exception as e:
            logger.critical(f"SYNC FAILURE: Database out of alignment with bot state! {e}")
            raise e

    def calculate_total_equity(self, current_prices: dict):
        """
        Calculates total equity across all positions.
        current_prices: dict of {ticker: price}
        """
        query = f"SELECT asset_name, holdings, cash_balance FROM `{self.table_id}`"
        results = list(self.client.query(query).result())
        
        total_cash = 0.0
        total_market_value = 0.0
        breakdown = []
        
        for row in results:
            ticker = row.asset_name
            cash = row.cash_balance
            holdings = row.holdings
            
            # Use current price if available, otherwise 0 (conservative)
            price = current_prices.get(ticker, 0.0)
            market_value = holdings * price
            
            total_cash += cash
            total_market_value += market_value
            
            breakdown.append({
                "ticker": ticker,
                "cash": cash,
                "holdings": holdings,
                "market_value": market_value
            })
            
        total_equity = total_cash + total_market_value
        
        logger.info(f"💰 Total Equity: ${total_equity:.2f} (Cash: ${total_cash:.2f}, Assets: ${total_market_value:.2f})")
        
        return {
            "total_equity": total_equity,
            "total_cash": total_cash,
            "total_market_value": total_market_value,
            "breakdown": breakdown
        }
