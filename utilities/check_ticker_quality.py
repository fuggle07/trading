import asyncio
import os
import sys
from bot.fundamental_agent import FundamentalAgent
from bot.telemetry import logger

# Mock logger to output to stdout
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

async def check_tickers(tickers):
    agent = FundamentalAgent()
    print(f"{'TICKER':<10} | {'SCORE':<5} | {'RATING':<10} | {'REASON'}")
    print("-" * 60)
    
    for ticker in tickers:
        try:
            is_deep, reason, f_score = await agent.evaluate_deep_health(ticker)
            
            # Extract Quality Score from reason string for display
            import re
            q_match = re.search(r"Quality (\d+)/100", reason)
            q_score = int(q_match.group(1)) if q_match else 0
            
            rating = "✅ BUY" if is_deep else "❌ AVOID"
            
            print(f"{ticker:<10} | {q_score:<5} | {rating:<10} | {reason}")
        except Exception as e:
            print(f"{ticker:<10} | {'ERR':<5} | {'ERROR':<10} | {str(e)}")

if __name__ == "__main__":
    allowed_tickers = sys.argv[1:]
    if not allowed_tickers:
        print("Usage: python3 check_ticker_quality.py TICKER1 TICKER2 ...")
        sys.exit(1)
    
    asyncio.run(check_tickers(allowed_tickers))
