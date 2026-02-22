import sys
import os
import unittest
from unittest.mock import MagicMock

# Ensure bot directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from bot.signal_agent import SignalAgent


class TestHedgeScaling(unittest.TestCase):
    def setUp(self):
        self.agent = SignalAgent()

    def test_hedge_caution_vix(self):
        """Test 2% hedge when VIX is elevated (> 30)."""
        macro_data = {
            "vix": 32.0,
            "indices": {"qqq_price": 400.0, "qqq_sma50": 390.0},  # Bullish trend
        }
        status, pct = self.agent.evaluate_macro_hedge(macro_data)
        self.assertEqual(status, "BUY_HEDGE")
        self.assertEqual(pct, 0.02)

    def test_hedge_caution_trend(self):
        """Test 2% hedge when trend is bearish but VIX is low."""
        macro_data = {
            "vix": 20.0,
            "indices": {"qqq_price": 380.0, "qqq_sma50": 390.0},  # Bearish trend
        }
        status, pct = self.agent.evaluate_macro_hedge(macro_data)
        self.assertEqual(status, "BUY_HEDGE")
        self.assertEqual(pct, 0.02)

    def test_hedge_fear(self):
        """Test 5% hedge when trend is bearish AND VIX > 35."""
        macro_data = {
            "vix": 36.0,
            "indices": {"qqq_price": 380.0, "qqq_sma50": 390.0},  # Bearish trend
        }
        status, pct = self.agent.evaluate_macro_hedge(macro_data)
        self.assertEqual(status, "BUY_HEDGE")
        self.assertEqual(pct, 0.05)

    def test_hedge_panic(self):
        """Test 10% hedge when VIX > 45."""
        macro_data = {"vix": 48.0, "indices": {"qqq_price": 400.0, "qqq_sma50": 390.0}}
        status, pct = self.agent.evaluate_macro_hedge(macro_data)
        self.assertEqual(status, "BUY_HEDGE")
        self.assertEqual(pct, 0.10)

    def test_hedge_clear(self):
        """Test clearing hedge when market is healthy."""
        macro_data = {"vix": 18.0, "indices": {"qqq_price": 410.0, "qqq_sma50": 390.0}}
        status, pct = self.agent.evaluate_macro_hedge(macro_data)
        self.assertEqual(status, "CLEAR_HEDGE")
        self.assertEqual(pct, 0.0)


if __name__ == "__main__":
    unittest.main()
