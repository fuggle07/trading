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

    def test_hedge_entry(self):
        """Test hedge entry scaling when VIX is simply over 28."""
        macro_data = {"vix": 30.0}
        status, pct = self.agent.evaluate_macro_hedge(macro_data, is_hedged=False)
        self.assertEqual(status, "BUY_HEDGE")
        # 30 VIX -> pct_range = 2. Slope = 0.08 / 22. 0.02 + (0.08/22)*2 = 0.027
        self.assertEqual(pct, 0.027)

    def test_hedge_stay_in_hysteresis(self):
        """Test hysteresis holding position when VIX drops below entry (28) but above exit (25)."""
        macro_data = {"vix": 26.0}
        status, pct = self.agent.evaluate_macro_hedge(macro_data, is_hedged=True)
        self.assertEqual(status, "BUY_HEDGE")
        # 26 is below 28, but effective VIX defaults to 28 minimum when hedged and above 25.
        self.assertEqual(pct, 0.02)

    def test_hedge_no_entry_low_vix(self):
        """Test that we do not enter if VIX is below entry (28)."""
        macro_data = {"vix": 26.0}
        status, pct = self.agent.evaluate_macro_hedge(macro_data, is_hedged=False)
        self.assertEqual(status, "CLEAR_HEDGE")
        self.assertEqual(pct, 0.0)

    def test_hedge_exit_hysteresis(self):
        """Test clearing hedge when VIX drops below exit threshold (25)."""
        macro_data = {"vix": 24.0}
        status, pct = self.agent.evaluate_macro_hedge(macro_data, is_hedged=True)
        self.assertEqual(status, "CLEAR_HEDGE")
        self.assertEqual(pct, 0.0)

    def test_hedge_panic_capped(self):
        """Test 10% maximum hedge when VIX exceeds max_vix (50)."""
        macro_data = {"vix": 60.0}
        status, pct = self.agent.evaluate_macro_hedge(macro_data)
        self.assertEqual(status, "BUY_HEDGE")
        self.assertEqual(pct, 0.10)


if __name__ == "__main__":
    unittest.main()
