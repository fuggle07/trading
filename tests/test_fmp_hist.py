import asyncio
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
FMP_KEY = os.getenv("FMP_KEY")

async def test():
    async with aiohttp.ClientSession() as session:
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/AAPL?apikey={FMP_KEY}"
        async with session.get(url) as resp:
            print(resp.status)
            data = await resp.json()
            print(data.keys() if isinstance(data, dict) else type(data))
            if "historical" in data:
                print(data["historical"][0])

asyncio.run(test())
