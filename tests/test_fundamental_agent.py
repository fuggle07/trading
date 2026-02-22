import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure bot directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from bot.fundamental_agent import FundamentalAgent


class TestFundamentalAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.agent = FundamentalAgent()

    @patch(
        "bot.fundamental_agent.FundamentalAgent.get_fundamentals",
        new_callable=AsyncMock,
    )
    async def test_evaluate_health_success(self, mock_get):
        """Test basic health calculation with mock fundamentals."""
        mock_get.return_value = {"pe_ratio": 25.0, "eps": 5.0, "market_cap": 1000000000}

        is_healthy, reason = await self.agent.evaluate_health("NVDA")
        self.assertTrue(is_healthy)
        self.assertIn("Healthy", reason)

    @patch(
        "bot.fundamental_agent.FundamentalAgent.evaluate_health", new_callable=AsyncMock
    )
    @patch(
        "bot.fundamental_agent.FundamentalAgent.fetch_annual_financials",
        new_callable=AsyncMock,
    )
    @patch("bot.fundamental_agent.FundamentalAgent._fetch_fmp", new_callable=AsyncMock)
    async def test_evaluate_deep_health_fcore(
        self, mock_fmp, mock_financials, mock_health
    ):
        """Test deep health F-Score calculation."""
        mock_health.return_value = (True, "Healthy")
        mock_financials.return_value = {
            "income": [
                {
                    "revenue": 1000,
                    "netIncome": 100,
                    "grossProfit": 500,
                    "weightedAverageShsOut": 10,
                },
                {
                    "revenue": 800,
                    "netIncome": 50,
                    "grossProfit": 300,
                    "weightedAverageShsOut": 10,
                },
            ],
            "balance": [
                {
                    "totalAssets": 500,
                    "totalLiabilities": 100,
                    "totalDebt": 100,
                    "totalCurrentAssets": 200,
                    "totalCurrentLiabilities": 100,
                },
                {
                    "totalAssets": 400,
                    "totalLiabilities": 120,
                    "totalDebt": 120,
                    "totalCurrentAssets": 150,
                    "totalCurrentLiabilities": 80,
                },
            ],
            "cash": [{"operatingCashFlow": 150}, {"operatingCashFlow": 100}],
        }
        self.agent.fmp_key = "MOCK_KEY"

        _, _, is_deep, reason, f_score = await self.agent.evaluate_deep_health("NVDA")
        self.assertIsInstance(is_deep, bool)
        self.assertIsInstance(f_score, int)
        self.assertIn("F-Score", reason)


if __name__ == "__main__":
    # Note: Running async tests in unittest requires some boilerplate
    # or using specialized runners like pytest-asyncio.
    # For CI we will use pytest.
    pass
