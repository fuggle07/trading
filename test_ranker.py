import asyncio
import os
import logging
from bot.ticker_ranker import TickerRanker
from google.cloud import bigquery

logging.basicConfig(level=logging.ERROR)

async def test_ranker():
    project_id = os.environ.get("PROJECT_ID")
    client = bigquery.Client()
    ranker = TickerRanker(project_id, client)
    res = await ranker.analyze_ticker("AAPL", "")
    print(res)

if __name__ == "__main__":
    asyncio.run(test_ranker())
