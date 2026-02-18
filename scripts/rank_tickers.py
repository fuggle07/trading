#!/usr/bin/env python3
import os
import asyncio
import logging
from google.cloud import bigquery
from bot.ticker_ranker import TickerRanker

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RankerScript")

# Configuration
# Actual Project ID: utopian-calling-429014-r9
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")
TICKERS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMD", "PLTR", "COIN"]

async def main():
    logger.info(f"🚀 Starting Morning Ticker Ranking for Project: {PROJECT_ID}")
    
    bq_client = bigquery.Client(project=PROJECT_ID)
    ranker = TickerRanker(PROJECT_ID, bq_client)
    
    # This now correctly logs to utopian-calling-429014-r9.trading_data.ticker_rankings
    results = await ranker.rank_and_log(TICKERS)
    
    # Sort for local display
    ranked = sorted(
        results, key=lambda x: (x.get("confidence", 0)), reverse=True
    )

    print("\n## 🚀 Daily Ticker Rankings (Logged to BigQuery)\n")
    print("| Rank | Ticker | Confidence | Sentiment | Reason |")
    print("|------|--------|------------|-----------|--------|")
    for i, res in enumerate(ranked, 1):
        sentiment = res.get("sentiment", 0.0)
        sent_icon = "📈" if sentiment > 0 else "📉" if sentiment < 0 else "😐"
        print(
            f"| {i} | **{res['ticker']}** | {res['confidence']}% | {sent_icon} {sentiment:.2f} | {res['reason']} |"
        )
    print("\n")

if __name__ == "__main__":
    asyncio.run(main())
