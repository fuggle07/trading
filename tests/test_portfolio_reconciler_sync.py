
import sys
import unittest
from unittest.mock import MagicMock, patch
import os

# Mock dependencies
sys.modules["alpaca"] = MagicMock()
sys.modules["alpaca.trading"] = MagicMock()
sys.modules["alpaca.trading.client"] = MagicMock()
sys.modules["alpaca.trading.requests"] = MagicMock()
sys.modules["alpaca.trading.enums"] = MagicMock()

# Ensure bot directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from bot.portfolio_reconciler import PortfolioReconciler

class TestPortfolioReconcilerSync(unittest.TestCase):
    def setUp(self):
        self.mock_bq = MagicMock()
        self.reconciler = PortfolioReconciler("test-project", self.mock_bq)
        # Mock Alpaca client
        self.reconciler.trading_client = MagicMock()

    def test_sync_executions_handles_streaming_buffer_error(self):
        """Test that streaming buffer error is swallowed and logged as info."""
        # 1. Mock Alpaca orders
        mock_order = MagicMock()
        mock_order.id = "order_123"
        mock_order.status = "filled"
        mock_order.filled_avg_price = 100.0
        mock_order.filled_qty = 10
        mock_order.symbol = "AAPL"
        
        self.reconciler.trading_client.get_orders.return_value = [mock_order]

        # 2. Mock BQ exception
        # We need to simulate the "streaming buffer" message in the exception string
        self.mock_bq.query.side_effect = Exception("UPDATE or DELETE statement over table ... would affect rows in the streaming buffer")

        # 3. Run sync
        # Should NOT raise exception
        try:
            self.reconciler.sync_executions()
        except Exception as e:
            self.fail(f"sync_executions raised exception: {e}")

        self.mock_bq.query.assert_called_once()
        query_text = self.mock_bq.query.call_args[0][0]
        self.assertIn("'order_123'", query_text)
        self.assertIn("FILLED_CONFIRMED", query_text)

    def test_sync_executions_other_error(self):
        """Test that other BQ errors are still logged as errors (re-raised or logged)."""
        mock_order = MagicMock()
        mock_order.id = "order_456"
        mock_order.status = "filled"
        mock_order.symbol = "TSLA"
        self.reconciler.trading_client.get_orders.return_value = [mock_order]

        self.mock_bq.query.side_effect = Exception("Table not found")

        # Reconciler logs the error but doesn't raise it to prevent bot crash
        with self.assertLogs(level="ERROR") as cm:
            self.reconciler.sync_executions()
        self.assertTrue(any("Execution Bulk Sync Failed" in line for line in cm.output))

if __name__ == "__main__":
    unittest.main()
