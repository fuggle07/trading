import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal

# Ensure bot directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from bot.signal_agent import SignalAgent


class TestSignalAgent(unittest.TestCase):
    def setUp(self):
        # Initialize with standard thresholds
        self.agent = SignalAgent(vol_threshold=0.35, hurdle_rate=0.015)
        # Mock is_market_open to True for deterministic testing
        self.agent.is_market_open = MagicMock(return_value=True)
        # Mock should_exit to HOLD by default so it doesn't interfere
        self.agent.should_exit = MagicMock(return_value="HOLD")

    def test_evaluate_bands_buy(self):
        """Test technical BUY signal when price is at or below lower band."""
        signal = self.agent.evaluate_bands(90.0, 120.0, 100.0)
        self.assertEqual(signal, "BUY")

    def test_evaluate_bands_sell(self):
        """Test technical SELL signal when price is at or above upper band."""
        signal = self.agent.evaluate_bands(130.0, 120.0, 100.0)
        self.assertEqual(signal, "SELL")

    def test_evaluate_bands_volatile(self):
        """Test that wide bands trigger VOLATILE_IGNORE unconditionally (strict cap)."""
        # Price 100, Width = (140-80)/100 = 60%.  Limit is 35%.
        signal = self.agent.evaluate_bands(100.0, 140.0, 80.0, is_low_exposure=True)
        self.assertEqual(signal, "VOLATILE_IGNORE")

    def test_momentum_breakout(self):
        """Test momentum breakout overlay triggers a BUY on high volume and price above band."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 125.0,
            "bb_lower": 100.0,
            "bb_upper": 120.0,
            "sentiment_score": 0.6,
            "volume": 200,
            "avg_volume": 100,  # 2.0x avg volume
            "f_score": 7,
            "prediction_confidence": 75,
            "is_healthy": True,
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "BUY")
        self.assertEqual(decision["meta"]["technical"], "MOMENTUM_BREAKOUT")

    def test_earnings_calendar_avoidANCE(self):
        """Verify skip if earnings are within 3 days."""
        market_data = {
            "ticker": "AAPL",
            "current_price": 100.0,
            "bb_lower": 110.0,  # Forces BUY
            "bb_upper": 130.0,
            "sentiment_score": 0.8,
            "days_to_earnings": 2,  # Near earnings
            "is_healthy": True,
            "f_score": 7,
            "prediction_confidence": 80,
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "IDLE")
        self.assertTrue(decision["meta"]["technical"].startswith("SKIP_EARNINGS"))

    def test_strategic_exit(self):
        """Verify should_exit triggers a SELL_ALL even against strong technicals."""
        self.agent.should_exit.return_value = "SELL_ALL"
        market_data = {
            "ticker": "NVDA",
            "current_price": 150.0,
            "avg_price": 100.0,  # Triggers exit logic
            "bb_lower": 100.0,
            "bb_upper": 200.0,  # Middle of band
            "sentiment_score": 0.9,
            "is_healthy": True,
            "f_score": 9,
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "SELL_ALL")
        self.assertEqual(decision["meta"]["technical"], "STAR_EXIT_SELL_ALL")

    def test_rsi_extreme_overbought(self):
        """Verify RSI > 85 forces a SELL_ALL when holding."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 150.0,
            "avg_price": 100.0,
            "bb_lower": 100.0,
            "bb_upper": 200.0,
            "sentiment_score": 0.5,
            "rsi": 88.0,  # Extreme overbought
            "is_healthy": True,
            "f_score": 5,
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "SELL_ALL")
        self.assertEqual(decision["meta"]["technical"], "RSI_EXTREME_OVERBOUGHT")

    def test_missing_data_rejection(self):
        """Test rejection when F_score is None and AI score is low."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 100.0,
            "bb_lower": 110.0,  # Forces BUY
            "bb_upper": 130.0,
            "sentiment_score": 0.5,
            "is_healthy": True,
            "f_score": None,  # Missing data
            "prediction_confidence": 60,  # Set directly to < 70
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "IDLE")
        self.assertEqual(decision["meta"]["technical"], "REJECT_INSUFFICIENT_DATA")

    def test_turnaround_play(self):
        """Test turnaround play for bad f_score if AI conviction is high."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 100.0,
            "bb_lower": 110.0,  # Forces BUY
            "bb_upper": 130.0,
            "sentiment_score": 0.6,  # AI score effectively 80
            "is_healthy": True,
            "f_score": 1,
            "prediction_confidence": 80,
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "BUY")
        self.assertTrue("TURNAROUND_WARRANTED" in decision["meta"]["technical"])

    def test_fscore_3_bypass(self):
        """Test intermediate f_score bypass with high AI score."""
        market_data = {
            "ticker": "NVDA",
            "current_price": 100.0,
            "bb_lower": 110.0,
            "bb_upper": 130.0,
            "sentiment_score": 0.8,
            "is_healthy": True,
            "f_score": 3,
            "prediction_confidence": 85,  # High AI score bypasses low f_score
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertEqual(decision["action"], "BUY")
        self.assertEqual(decision["meta"]["technical"], "BUY_FSCORE_3_BYPASS")

    def test_star_rating_classification(self):
        """Test star rating classification requires score>=85 and f_score>=7 and is_deep_healthy."""
        market_data = {
            "ticker": "LLY",
            "current_price": 100.0,
            "bb_lower": 110.0,
            "bb_upper": 130.0,
            "sentiment_score": 0.8,
            "is_healthy": True,
            "is_deep_healthy": True,
            "f_score": 8,
            "prediction_confidence": 88,
            "is_low_exposure": True,
        }
        decision = self.agent.evaluate_strategy(market_data)
        self.assertTrue(decision["meta"]["is_star"])
        self.assertTrue(decision["meta"]["technical"].startswith("STAR_"))


if __name__ == "__main__":
    unittest.main()
