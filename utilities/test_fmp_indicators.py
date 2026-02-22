import os
import asyncio
import aiohttp
from bot.fundamental_agent import FundamentalAgent
from bot.telemetry import logger


async def test_indicators():
    ticker = "NVDA"
    agent = FundamentalAgent()

    if not agent.fmp_key:
        print("❌ FMP_KEY not set in environment.")
        return

    print(f"--- 📡 Testing FMP Indicators for {ticker} ---")

    # 1. Test SMA(20)
    sma20 = await agent.get_technical_indicator(ticker, "sma", period=20)
    if sma20:
        print(f"✅ SMA(20): {sma20.get('sma')} (Date: {sma20.get('date')})")
    else:
        print("❌ SMA(20) failed.")

    # 2. Test RSI(14)
    rsi14 = await agent.get_technical_indicator(ticker, "rsi", period=14)
    if rsi14:
        print(f"✅ RSI(14): {rsi14.get('rsi')} (Date: {rsi14.get('date')})")
    else:
        print("❌ RSI(14) failed.")

    # 3. Test Standard Deviation(20)
    std20 = await agent.get_technical_indicator(ticker, "standarddeviation", period=20)
    if std20:
        print(
            f"✅ StdDev(20): {std20.get('standardDeviation')} (Date: {std20.get('date')})"
        )
    else:
        print("❌ StdDev(20) failed.")


if __name__ == "__main__":
    asyncio.run(test_indicators())
