import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
from bot.fundamental_agent import FundamentalAgent
import finnhub


async def main():
    agent = FundamentalAgent()
    quotes = await agent.get_batch_quotes(["PSQ"])
    print("FMP:", quotes)

    finnhub_client = finnhub.Client(api_key=os.environ.get("EXCHANGE_API_KEY"))
    try:
        fh_quote = finnhub_client.quote("PSQ")
        print("Finnhub:", fh_quote)
    except Exception as e:
        print("Finnhub error:", e)


if __name__ == "__main__":
    asyncio.run(main())
