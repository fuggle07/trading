import logging
import os
import time
import random

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
            avg_price = (
                results[0].avg_price if results[0].avg_price is not None else 0.0
            )
            return {
                "holdings": results[0].holdings,
                "cash_balance": results[0].cash_balance,
                "avg_price": avg_price,
            }

        # High-resolution safety: No default values for real capital
        raise ValueError(
            f"Portfolio ledger empty for {ticker}. Initialization required."
        )

    def ensure_portfolio_state(self, ticker):
        """
        Ensures the portfolio table is seeded.
        - Checks for 'USD' asset (Global Cash Pool). If missing, seeds with $50,000.
        - For other tickers, ensures they exist with 0 holdings / 0 cash (legacy column).
        """
        try:
            # 1. Ensure Global Cash ('USD')
            query = f"SELECT asset_name FROM `{self.table_id}` WHERE asset_name = 'USD'"
            results = list(self.client.query(query).result(timeout=10))

            if not results:
                initial_cash = float(os.getenv("INITIAL_CASH", 50000.0))
                logger.info(
                    f"💰 Seeding GLOBAL CASH POOL (USD) with ${initial_cash:,.2f}"
                )
                dml = f"""
                INSERT INTO `{self.table_id}` (asset_name, holdings, cash_balance, avg_price, last_updated)
                VALUES ('USD', 0.0, {initial_cash}, 0.0, CURRENT_TIMESTAMP())
                """
                self.client.query(dml).result(timeout=10)

            # 2. Ensure Ticker Entry (if not USD)
            if ticker != "USD":
                query = f"SELECT asset_name FROM `{self.table_id}` WHERE asset_name = '{ticker}'"
                results = list(self.client.query(query).result(timeout=10))

                if not results:
                    logger.info(f"🌱 Seeding ledger for {ticker} (0 Holdings)")
                    dml = f"""
                    INSERT INTO `{self.table_id}` (asset_name, holdings, cash_balance, avg_price, last_updated)
                    VALUES ('{ticker}', 0.0, 0.0, 0.0, CURRENT_TIMESTAMP())
                    """
                    self.client.query(dml).result(timeout=10)

        except Exception as e:
            logger.error(f"Failed to ensure portfolio state for {ticker}: {e}")

    def get_cash_balance(self):
        """Fetches the global cash balance (USD)."""
        query = f"SELECT cash_balance FROM `{self.table_id}` WHERE asset_name = 'USD' LIMIT 1"
        results = list(self.client.query(query).result(timeout=10))
        return results[0].cash_balance if results else 0.0

    def update_ledger(self, ticker, cash_delta, holdings_delta, price, action):
        """
        Updates ledger with Unified Cash Pool logic.
        - Updates 'USD' row for cash changes.
        - Updates 'TICKER' row for holding changes & Weighted Average Cost.
        """
        # 1. Get current ticker state for WAC
        try:
            current_state = self.get_state(ticker)
            old_holdings = current_state["holdings"]
            old_avg = current_state["avg_price"]
        except Exception:
            old_holdings = 0.0
            old_avg = 0.0

        # 2. Calculate New Average Price
        new_avg = old_avg
        new_holdings = old_holdings + holdings_delta

        if action == "BUY" and holdings_delta > 0:
            # Weighted Average Cost: ((OldShares * OldAvg) + (NewShares * BuyPrice)) / TotalShares
            total_cost = (old_holdings * old_avg) + (holdings_delta * price)
            new_avg = total_cost / new_holdings if new_holdings > 0 else 0.0

        if new_holdings == 0:
            new_avg = 0.0

        # 3. Construct Transaction Query
        # Wrap updates in a retry block with exponential backoff to handle DML table locking
        # concurrent updates across WebSocket events.
        max_retries = 6
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                # BQ Scripting: combine both updates in a single execution job.
                script_dml = f"""
                UPDATE `{self.table_id}`
                SET holdings = {new_holdings},
                avg_price = {new_avg},
                last_updated = CURRENT_TIMESTAMP()
                WHERE asset_name = '{ticker}';
                
                UPDATE `{self.table_id}`
                SET cash_balance = cash_balance + ({cash_delta}),
                last_updated = CURRENT_TIMESTAMP()
                WHERE asset_name = 'USD';
                """

                self.client.query(script_dml).result(timeout=15)
                logger.info(
                    f"Ledger Sync: {ticker} | Holdings: {new_holdings} | Avg: ${new_avg:.2f} | Cash Delta: ${cash_delta:.2f}"
                )
                break
            except Exception as e:
                if "concurrent update" in str(e).lower() and attempt < max_retries - 1:
                    sleep_time = base_delay * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Concurrent BQ update detected for {ticker}. Retrying in {sleep_time:.2f}s... (Attempt {attempt+1}/{max_retries})"
                    )
                    time.sleep(sleep_time)
                else:
                    logger.critical(f"SYNC FAILURE: Database transaction failed! {e}")
                    raise e

    def calculate_total_equity(self, current_prices: dict):
        """
        Calculates total equity across all positions.
        current_prices: dict of {ticker: price}
        """
        query = f"SELECT asset_name, holdings, cash_balance, avg_price FROM `{self.table_id}`"
        results = list(self.client.query(query).result())

        total_cash = 0.0
        total_market_value = 0.0
        breakdown = []

        for row in results:
            ticker = row.asset_name
            cash = row.cash_balance
            holdings = row.holdings
            avg_price = getattr(row, "avg_price", 0.0)

            # Special handling for USD
            if ticker == "USD":
                total_cash += cash
                continue

            # Use current price if available, otherwise 0 (conservative)
            price = current_prices.get(ticker, 0.0)
            market_value = holdings * price

            # USD already added to total_cash above; ticker rows shouldn't have cash_balance but we sum if they do
            # (though in this architecture, only USD row holds global cash)
            # total_cash += cash  <-- Removing this to prevent double-count if legacy rows exist
            total_market_value += market_value

            breakdown.append(
                {
                    "ticker": ticker,
                    "cash": cash,
                    "holdings": holdings,
                    "market_value": market_value,
                    "avg_price": avg_price if avg_price is not None else 0.0,
                }
            )

        total_equity = total_cash + total_market_value

        logger.info(
            f"💰 Total Equity: ${total_equity:.2f} (Cash: ${total_cash:.2f}, Assets: ${total_market_value:.2f})"
        )

        return {
            "total_equity": total_equity,
            "total_cash": total_cash,
            "total_market_value": total_market_value,
            "breakdown": breakdown,
        }

    def get_held_tickers(self):
        """Returns a dict of {ticker: holdings} for assets where holdings > 0."""
        query = f"SELECT asset_name, holdings FROM `{self.table_id}` WHERE holdings > 0 AND asset_name != 'USD'"
        results = list(self.client.query(query).result())
        return {row.asset_name: row.holdings for row in results}
