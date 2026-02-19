import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime
import pytz

# Ensure bot directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from bot.signal_agent import SignalAgent

class TestSignalAgent(unittest.TestCase):
    def setUp(self):
        # Initialize with standard thresholds
        self.agent = SignalAgent(
            vol_threshold=0.35,
            hurdle_rate=0.015
        )
        # Mock is_market_open to True for deterministic testing
        self.agent.is_market_open = MagicMock(return_value=True)

    def test_evaluate_bands_buy(self):
        """Test technical BUY signal when price is at or below lower band."""
        # Price 90, Lower 100, Upper 120 -> BUY
        signal = self.agent.evaluate_bands(90.0, 120.0, 100.0)
        self.assertEqual(signal, "BUY")

    def test_evaluate_bands_sell(self):
        """Test technical SELL signal when price is at or above upper band."""
        # Price 130, Lower 100, Upper 120 -> SELL
        signal = self.agent.evaluate_bands(130.0, 120.0, 100.0)
        self.assertEqual(signal, "SELL")

    def test_evaluate_bands_volatile(self):
        """Test that wide bands trigger VOLATILE_IGNORE."""
        # Price 100, Lower 80, Upper 140 -> Width = (140-80)/100 = 60% > 35%
        signal = self.agent.evaluate_bands(100.0, 140.0, 80.0)
        self.assertEqual(signal, "VOLATILE_IGNORE")

    def test_strategy_sentiment_gate(self):
        """Verify that low sentiment blocks a technical BUY."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 95.0,
            "bb_lower": 100.0,
            "bb_upper": 120.0,
            "sentiment_score": 0.2, # Below 0.4 gate
            "is_healthy": True,
            "f_score": 7
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "IDLE")
        self.assertEqual(decision["meta"]["technical"], "BUY") # Technically a buy, but gated

    def test_rsi_oversold_buy(self):
        """Verify that RSI <= 30 triggers a buy even if not at bands."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 110.0, # Middle of 100-120
            "bb_lower": 100.0,
            "bb_upper": 120.0,
            "sentiment_score": 0.5,
            "rsi": 25.0, # Oversold
            "is_healthy": True,
            "f_score": 7
        }
        decision = self.agent.evaluate_strategy(market_data)
        # Note: action might be OFF_MARKET_BUY if running after hours
        self.assertIn("BUY", decision["action"])
        self.assertEqual(decision["meta"]["technical"], "RSI_OVERSOLD_BUY")

    def test_low_exposure_aggression(self):
        """Verify HOLD_AGGRESSIVE_ENTRY when exposure is low."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 110.0,
            "bb_lower": 100.0,
            "bb_upper": 120.0,
            "sentiment_score": 0.7, # Elite sentiment
            "prediction_confidence": 75, # Elite health/score
            "is_low_exposure": True,
            "is_healthy": True,
            "f_score": 7
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertIn("BUY", decision["action"])
        self.assertEqual(decision["meta"]["technical"], "HOLD_AGGRESSIVE_ENTRY")

    def test_fundamental_rejection(self):
        """Verify that weak F-Score rejects a BUY."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 90.0,
            "bb_lower": 100.0,
            "bb_upper": 120.0,
            "sentiment_score": 0.8,
            "is_healthy": True,
            "f_score": 3 # Weak F-Score (< 5)
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "IDLE")
        self.assertEqual(decision["meta"]["technical"], "REJECT_WEAK_FSCORE_3")

if __name__ == "__main__":
    unittest.main()
