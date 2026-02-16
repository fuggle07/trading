import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os
import asyncio

# Add project root and bot directory to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'bot'))

# Mock dependencies BEFORE importing bot.main to avoid init errors
sys.modules['finnhub'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.bigquery'] = MagicMock()

# Import main after mocking
from bot import main

class TestTradingFlow(unittest.TestCase):

    def setUp(self):
        # Mock clients
        self.mock_finnhub = MagicMock()
        self.mock_bq = MagicMock()
        
        # Patch them in main
        main.finnhub_client = self.mock_finnhub
        main.bq_client = self.mock_bq
        
        # Reset agents to ensure fresh state
        import bot.signal_agent
        import bot.execution_manager
        main.signal_agent = bot.signal_agent.SignalAgent()
        main.execution_manager = bot.execution_manager.ExecutionManager()
        # Mock execution manager's internal bq client so it doesn't try to connect
        main.execution_manager.bq_client = MagicMock()

    @patch('bot.main.log_watchlist_data')
    def test_run_audit_flow(self, mock_log):
        # 1. Setup Mock Data (70 days of rising prices to trigger Golden Cross)
        # We need a clear crossover: SMA20 > SMA50
        dates = pd.date_range(end=pd.Timestamp.now(), periods=70, freq='D')
        
        # Scenario: 
        # First 40 days: Flat at 100
        # Last 30 days: Flat at 102 (Step up)
        # This causes SMA20 to rise to 102 quickly, while SMA50 lags at ~100.8
        # Volatility (StdDev) of last 20 days will be 0 (since it's flat at 102), so it passes vol check.
        prices = [100.0] * 40 + [102.0] * 30 
        
        mock_candles = {
            's': 'ok',
            't': [int(d.timestamp()) for d in dates],
            'c': prices,
            'h': prices,
            'l': prices,
            'o': prices,
            'v': [1000] * 70
        }
        
        self.mock_finnhub.stock_candles.return_value = mock_candles

        # 2. Run the Audit
        # We use asyncio.run to execute the async function
        results = asyncio.run(main.run_audit())

        # 3. Verify Results
        # Check if fetch_historical_data was called
        self.mock_finnhub.stock_candles.assert_called()
        
        # Check if we got results
        self.assertTrue(len(results) > 0)
        
        # Check if at least one trade was executed (Golden Cross scenario)
        executed_trades = [r for r in results if 'executed' in r.get('status', '')]
        self.assertTrue(len(executed_trades) > 0, "Expected at least one executed trade")
        
        print(f"✅ Executed {len(executed_trades)} trades in test.")
        for trade in executed_trades:
            print(f"   -> {trade['ticker']}: {trade['signal']['action']} @ {trade['price']}")

if __name__ == '__main__':
    unittest.main()
