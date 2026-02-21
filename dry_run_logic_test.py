import sys
import os
import asyncio
from unittest.mock import patch, MagicMock

# Load .env if it exists
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

# Set up mock environment
os.environ["TRADING_ENABLED"] = "false"
os.environ["EXCHANGE_API_KEY"] = "mock_key"
os.environ["ALPACA_API_KEY"] = "mock_key"
os.environ["ALPACA_API_SECRET"] = "mock_key"
os.environ["PROJECT_ID"] = "mock-project"

# Mock Heavy Imports to avoid connectivity issues
mock_bq = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.bigquery'] = mock_bq
sys.modules['alpaca.trading.client'] = MagicMock()
sys.modules['alpaca.data.historical'] = MagicMock()
sys.modules['alpaca.data.requests'] = MagicMock()
sys.modules['alpaca.data.timeframe'] = MagicMock()

# Ensure we don't try to actually connect to anything
with patch('bot.portfolio_reconciler.PortfolioReconciler'), \
     patch('bot.ticker_ranker.TickerRanker'), \
     patch('bot.feedback_agent.FeedbackAgent'), \
     patch('bot.fundamental_agent.FundamentalAgent'), \
     patch('bot.sentiment_analyzer.SentimentAnalyzer'), \
     patch('bot.portfolio_manager.PortfolioManager') as MockPM:

    # Configure the Mock Portfolio Manager
    pm_instance = MockPM.return_value
    pm_instance.get_held_tickers.return_value = {"TSLA": 10} # Holding 10 shares of TSLA
    pm_instance.get_cash_balance.return_value = 50000.0
    
    # Import the bot components
    import bot.main as main
    
    async def mocked_run_audit():
        # Override some of main's globals or functions if needed
        # For a true dry run of 'Phase 2 & 3', we mock the data inputs of run_audit
        
        # 1. Mock get_macro_context to return a 'FEAR' scenario
        with patch('bot.main.get_macro_context', new_callable=MagicMock) as mock_macro, \
             patch('bot.main.fetch_historical_data') as mock_hist, \
             patch('bot.main.fetch_ticker_intelligence') as mock_intel, \
             patch('bot.main.fundamental_agent') as mock_fa, \
             patch('bot.main.reconciler') as mock_rec:
            
            mock_macro.return_value = {
                "vix": 36.0,
                "indices": {"qqq_price": 380.0, "qqq_sma50": 390.0},
                "formatted": "Market Context: FEAR (VIX 36, Bearish Trend)"
            }
            
            # Mock pricing data
            mock_fa.get_batch_quotes.return_value = {
                "TSLA": {"price": 180.0, "changesPercentage": -2.0},
                "PSQ": {"price": 10.0, "changesPercentage": 1.5}
            }
            mock_fa.get_upcoming_earnings.return_value = {}
            
            # Mock intelligence for TSLA
            # Suppose it's dropping, but we haven't scaled out yet
            mock_intel.return_value = {
                "ticker": "TSLA",
                "confidence": 70,
                "current_price": 180.0,
                "sentiment": 0.5,
                "band_width": 0.1,
                "hwm": 200.0, # High was 200, now 180 (10% drop -> Trailing Stop should hit)
                "has_scaled_out": False
            }
            
            # Mock total equity
            # total_equity = cash (50000) + market_val (10 * 180 = 1800) = 51800
            
            print("🚀 Executing Strategic Logic Test...")
            print("Scenario: VIX 36 (Fear), Bearish Trend, TSLA dropping from HWM.")
            
            # Capture print outputs to see the decisions
            results = await main.run_audit()
            
            print("\n📋 DECISION LOG SUMMARY:")
            # Note: run_audit returns execution_results which we populated
            for res in results:
                print(f"[{res.get('ticker')}] SIGNAL: {res.get('signal')} | REASON: {res.get('reason')}")

    if __name__ == "__main__":
        asyncio.run(mocked_run_audit())
