import logging
import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

logger = logging.getLogger("PortfolioReconciler")


class PortfolioReconciler:
    """
    Syncs the BigQuery 'Portfolio' and 'Executions' tables with Alpaca's Source of Truth.
    Corrects drift caused by slippage, fees, or missed signals.
    """

    def __init__(self, project_id, bq_client):
        self.project_id = project_id
        self.bq_client = bq_client
        self.portfolio_table = f"{project_id}.trading_data.portfolio"
        self.executions_table = f"{project_id}.trading_data.executions"

        # Alpaca Setup
        self.alpaca_key = os.getenv("ALPACA_API_KEY")
        self.alpaca_secret = os.getenv("ALPACA_API_SECRET")
        self.trading_client = None

        if self.alpaca_key and self.alpaca_secret:
            try:
                self.trading_client = TradingClient(
                    self.alpaca_key, self.alpaca_secret, paper=True
                )
                logger.info("✅ Alpaca Client Connected for Reconciliation")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Alpaca: {e}")
        else:
            logger.warning("⚠️ Alpaca Keys missing. Reconciliation disabled.")

    def sync_portfolio(self):
        """
        Overwrites BigQuery ledger with Alpaca's actual Cash & Positions using bulk operations.
        """
        if not self.trading_client:
            return

        logger.info("🔄 Starting Bulk Portfolio Reconciliation...")

        try:
            # 1. Get Actuals from Alpaca
            account = self.trading_client.get_account()
            cash_balance = float(account.cash)
            positions = self.trading_client.get_all_positions()

            logger.info(
                f"Alpaca Truth: Cash=${cash_balance:.2f}, Positions={len(positions)}"
            )

            # 2. Prepare Data for Bulk Merge
            # We include Cash as a pseudo-position with 0 holdings and the actual cash_balance
            merge_data = [{"asset_name": "USD", "holdings": 0.0, "cash": cash_balance, "avg": 0.0}]
            for pos in positions:
                merge_data.append({
                    "asset_name": pos.symbol,
                    "holdings": float(pos.qty),
                    "cash": 0.0,
                    "avg": float(pos.avg_entry_price)
                })

            # 3. Construct Unified Bulk MERGE Query
            # First, wipe non-USD holdings to handle stocks no longer owned
            # Then merge the actual state
            
            # Using a single transaction or script for efficiency
            # We build the 'USING' clause dynamically
            values_clauses = []
            for item in merge_data:
                values_clauses.append(
                    f"SELECT '{item['asset_name']}' as asset_name, {item['holdings']} as holdings, {item['cash']} as cash, {item['avg']} as avg"
                )
            
            using_subquery = " UNION ALL ".join(values_clauses)

            bulk_query = f"""
                BEGIN TRANSACTION;
                -- 1. Logical Wipe (Zero out everything that isn't 'USD' so missing stocks are set to 0)
                UPDATE `{self.portfolio_table}` SET holdings = 0 WHERE asset_name != 'USD';

                -- 2. Bulk Merge Actuals
                MERGE `{self.portfolio_table}` T
                USING ({using_subquery}) S
                ON T.asset_name = S.asset_name
                WHEN MATCHED THEN
                  UPDATE SET holdings = S.holdings, cash_balance = S.cash, avg_price = S.avg, last_updated = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN
                  INSERT (asset_name, holdings, cash_balance, avg_price, last_updated)
                  VALUES (S.asset_name, S.holdings, S.cash, S.avg, CURRENT_TIMESTAMP());
                COMMIT TRANSACTION;
            """

            self.bq_client.query(bulk_query).result()
            logger.info(f"✅ Portfolio reconciled: {len(merge_data)} assets updated in bulk.")

        except Exception as e:
            logger.error(f"❌ Portfolio Sync Failed: {e}")

    def sync_executions(self, limit=50):
        """
        Updates recent 'executions' logs with actual fill prices and quantities in bulk.
        """
        if not self.trading_client:
            return

        try:
            # Get recent closed orders from Alpaca
            req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=limit)
            orders = self.trading_client.get_orders(req)

            fill_updates = []
            for order in orders:
                if order.status == "filled":
                    fill_updates.append({
                        "id": str(order.id),
                        "price": float(order.filled_avg_price) if order.filled_avg_price else 0.0,
                        "qty": float(order.filled_qty)
                    })

            if not fill_updates:
                return

            # Construct Bulk Update via MERGE
            values_clauses = [
                f"SELECT '{u['id']}' as oid, {u['price']} as p, {u['qty']} as q"
                for u in fill_updates
            ]
            using_subquery = " UNION ALL ".join(values_clauses)

            bulk_dml = f"""
                MERGE `{self.executions_table}` T
                USING ({using_subquery}) S
                ON T.alpaca_order_id = S.oid
                WHEN MATCHED AND T.status != 'FILLED_CONFIRMED' THEN
                  UPDATE SET price = S.p, quantity = S.q, commission = 0.0, status = 'FILLED_CONFIRMED';
            """
            
            job = self.bq_client.query(bulk_dml)
            job.result()
            
            if job.num_dml_affected_rows > 0:
                logger.info(f"✅ Sync'd {job.num_dml_affected_rows} execution records in bulk.")

        except Exception as e:
            err_str = str(e).lower()
            if "streaming buffer" in err_str:
                 logger.info("⏳ Skipping sync (some records still in BQ streaming buffer)")
            else:
                 logger.error(f"❌ Execution Bulk Sync Failed: {e}")
