import logging
import os
from google.cloud import bigquery
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, GetAccountActivitiesRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, ActivityType
from datetime import datetime, timezone

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
                self.trading_client = TradingClient(self.alpaca_key, self.alpaca_secret, paper=True)
                logger.info("✅ Alpaca Client Connected for Reconciliation")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Alpaca: {e}")
        else:
            logger.warning("⚠️ Alpaca Keys missing. Reconciliation disabled.")

    def sync_portfolio(self):
        """
        Overwrites BigQuery ledger with Alpaca's actual Cash & Positions.
        """
        if not self.trading_client:
            return

        logger.info("🔄 Starting Portfolio Reconciliation...")

        try:
            # 1. Get Actuals from Alpaca
            account = self.trading_client.get_account()
            cash_balance = float(account.cash)
            positions = self.trading_client.get_all_positions()
            
            logger.info(f"Alpaca Truth: Cash=${cash_balance:.2f}, Positions={len(positions)}")
            
            # 2. Logical Wipe of BQ Holdings (Set all to 0 first)
            # This ensures that if we sold something on Alpaca, BQ reflects 0 holdings.
            # Note: We don't delete rows, just zero them out to keep history/avg_price struct if needed (though avg_price doesn't matter for 0 holdings)
            wipe_query = f"""
                UPDATE `{self.portfolio_table}` 
                SET holdings = 0, last_updated = CURRENT_TIMESTAMP() 
                WHERE asset_name != 'USD'
            """
            self.bq_client.query(wipe_query).result()
            
            # 3. Update Cash (USD)
            # We assume 'USD' row exists (it should from PortfolioManager init)
            # If not, we insert it.
            cash_dml = f"""
                MERGE `{self.portfolio_table}` T
                USING (SELECT 'USD' as asset_name, {cash_balance} as cash) S
                ON T.asset_name = S.asset_name
                WHEN MATCHED THEN
                  UPDATE SET cash_balance = S.cash, last_updated = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN
                  INSERT (asset_name, holdings, cash_balance, avg_price, last_updated)
                  VALUES ('USD', 0.0, S.cash, 0.0, CURRENT_TIMESTAMP())
            """
            self.bq_client.query(cash_dml).result()
            
            # 4. Upsert Positions
            for pos in positions:
                ticker = pos.symbol
                qty = float(pos.qty)
                avg_entry = float(pos.avg_entry_price)
                
                # MERGE Statement for Atomic Upsert
                # We use MERGE to handle both INSERT (new stock) and UPDATE (existing stock)
                pos_dml = f"""
                    MERGE `{self.portfolio_table}` T
                    USING (SELECT '{ticker}' as asset_name, {qty} as holdings, {avg_entry} as avg) S
                    ON T.asset_name = S.asset_name
                    WHEN MATCHED THEN
                      UPDATE SET holdings = S.holdings, avg_price = S.avg, last_updated = CURRENT_TIMESTAMP()
                    WHEN NOT MATCHED THEN
                      INSERT (asset_name, holdings, cash_balance, avg_price, last_updated)
                      VALUES (S.asset_name, S.holdings, 0.0, S.avg, CURRENT_TIMESTAMP())
                """
                self.bq_client.query(pos_dml).result()
            
            logger.info("✅ Portfolio synced with Alpaca.")
            
        except Exception as e:
            logger.error(f"❌ Portfolio Sync Failed: {e}")

    def sync_executions(self, limit=50):
        """
        Updates recent 'executions' logs with actual fill prices, quantities, AND fees.
        Alpaca 'AccountActivity' is the source of truth for net_amount (fees).
        """
        if not self.trading_client:
            return

        try:
            # 1. Get recent closed orders
            req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=limit)
            orders = self.trading_client.get_orders(req)
            
            # 2. Get recent Account Activities to find actual fees
            # We look for 'FILL' activities which contain net_amount
            activity_req = GetAccountActivitiesRequest(activity_types=[ActivityType.FILL])
            activities = self.trading_client.get_account_activities(activity_req)
            
            # Map activities by order_id for quick lookup
            # Note: One order can have multiple fills, but for our simple bot we treat as one
            activity_map = {}
            for act in activities:
                order_id = getattr(act, 'order_id', None)
                if order_id:
                    activity_map[str(order_id)] = act

            updates = 0
            for order in orders:
                if order.status == 'filled':
                    alpaca_id = str(order.id)
                    filled_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
                    filled_qty = float(order.filled_qty)
                    
                    # Calculate Actual Fee from net_amount
                    # net_amount = (qty * price) + fees (where fees are negative for costs)
                    # For Alpaca AccountActivity:
                    # Buys: net_amount is negative (e.g., -100.05 for $100 stock + $0.05 fee)
                    # Sells: net_amount is positive (e.g., 99.95 for $100 stock - $0.05 fee)
                    actual_fee = 0.0
                    if alpaca_id in activity_map:
                        act = activity_map[alpaca_id]
                        net_amount = float(act.net_amount)
                        gross_amount = filled_qty * filled_price
                        
                        # Fee is the difference that went towards Alpaca/Regulators
                        actual_fee = abs(abs(net_amount) - gross_amount)
                    
                    # Update BQ where alpaca_order_id matches
                    # We overwrite 'price', 'quantity', 'commission' (actual_fee), and 'status'
                    dml = f"""
                        UPDATE `{self.executions_table}`
                        SET price = {filled_price}, 
                            quantity = {filled_qty}, 
                            commission = {actual_fee},
                            status = 'FILLED_CONFIRMED'
                        WHERE alpaca_order_id = '{alpaca_id}'
                        AND status != 'FILLED_CONFIRMED'
                    """
                    job = self.bq_client.query(dml)
                    res = job.result()
                    if job.num_dml_affected_rows > 0:
                        updates += 1
                        logger.info(f"[{order.symbol}] ✅ Updated sync: Price={filled_price}, Fee=${actual_fee:.4f}")
            
            if updates > 0:
                logger.info(f"✅ Total: Synced {updates} execution records with actual fill & fee data.")
                
        except Exception as e:
            logger.error(f"❌ Execution Sync Failed: {e}")
