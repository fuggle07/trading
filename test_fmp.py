import asyncio
import os
import aiohttp
import json

async def main():
    fmp_key = os.getenv("FMP_KEY")
    url = f"https://financialmodelingprep.com/api/v4/insider-trading?symbol=NVDA&limit=100&apikey={fmp_key}"
    url_search = f"https://financialmodelingprep.com/stable/insider-trading/search?limit=100&symbol=NVDA&apikey={fmp_key}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url_search) as response:
            print("Status stable:", response.status)
            if response.status == 200:
                data = await response.json()
                print("stable sample:", json.dumps(data[:2], indent=2))
                
        async with session.get(url) as response:
            print("Status v4:", response.status)
            if response.status == 200:
                data = await response.json()
                print("v4 sample:", json.dumps(data[:2], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
