import asyncio
from bot.main import fetch_historical_data
from bot.main import ALPACA_KEY, ALPACA_SECRET

async def main():
    print(f"ALPACA_KEY: {bool(ALPACA_KEY)}")
    print(f"ALPACA_SECRET: {bool(ALPACA_SECRET)}")
    try:
        val = await fetch_historical_data("LMT")
        print(f"Result length: {len(val) if val is not None else None}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
