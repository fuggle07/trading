import asyncio
import os
import aiohttp

async def main():
    fmp_key = os.getenv("FMP_KEY")
    if not fmp_key:
        from dotenv import load_dotenv
        load_dotenv()
        fmp_key = os.getenv("FMP_KEY")
    
    urls = [
        f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={fmp_key}",
        f"https://financialmodelingprep.com/v3/profile/AAPL?apikey={fmp_key}",
        f"https://financialmodelingprep.com/api/v3/technical_indicator/1day/AAPL?type=sma&period=20&apikey={fmp_key}",
        f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={fmp_key}"
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in urls:
            async with session.get(url) as resp:
                print(f"{url[:60]}... -> {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"Data snippet: {str(data)[:100]}")
                else:
                    text = await resp.text()
                    print(f"Error: {text[:100]}")

asyncio.run(main())
