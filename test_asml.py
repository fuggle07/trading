import asyncio
from bot.fundamental_agent import FundamentalAgent


async def main():
    fa = FundamentalAgent()
    res = await fa.evaluate_deep_health("ASML")
    print(res)


asyncio.run(main())
