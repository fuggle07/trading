import asyncio
from bot.main import fetch_historical_fallback

async def main():
    val = await fetch_historical_fallback("LMT")
    print(val)

asyncio.run(main())
