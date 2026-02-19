import asyncio
import os
import aiohttp

async def test_endpoint(session, url, name):
    async with session.get(url) as response:
        status = response.status
        try:
            data = await response.json()
            is_error = isinstance(data, dict) and ("Error Message" in data or "error" in data)
            msg = data.get("Error Message") or data.get("error") if is_error else "OK"
        except:
            msg = "PARSE ERROR"
            is_error = True
        
        print(f"[{name}] Status: {status} | Info: {msg}")

async def run_tests():
    api_key = os.environ.get("FMP_KEY")
    if not api_key:
        print("❌ FMP_KEY not found in environment.")
        return

    async with aiohttp.ClientSession() as session:
        endpoints = [
            ("Technical RSI", f"https://financialmodelingprep.com/stable/technical-indicators/rsi?symbol=NVDA&periodLength=14&timeframe=1day&apikey={api_key}"),
            ("Historical Social Sentiment", f"https://financialmodelingprep.com/stable/social-sentiment/historical?symbol=NVDA&apikey={api_key}"),
            ("Insider Trading", f"https://financialmodelingprep.com/api/v3/insider-trading?symbol=NVDA&apikey={api_key}"),
            ("Earnings Transcript", f"https://financialmodelingprep.com/api/v3/earnings_transcript/NVDA?year=2024&quarter=3&apikey={api_key}"),
            ("Earnings Transcript List", f"https://financialmodelingprep.com/api/v3/earnings_transcript_list/NVDA?apikey={api_key}"),
            ("Stock News Sentiment", f"https://financialmodelingprep.com/api/v4/stock-news-sentiments-rss-feed?page=0&apikey={api_key}"),
        ]
        
        tasks = [test_endpoint(session, url, name) for name, url in endpoints]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(run_tests())
