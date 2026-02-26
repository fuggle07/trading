import asyncio
from bot.main import fetch_historical_data

async def main():
    val = await fetch_historical_data("LMT")
    print(f"Result type: {type(val)} - length: {len(val) if val is not None else 'None'}")
    if val is not None:
        print(val.head())

asyncio.run(main())
