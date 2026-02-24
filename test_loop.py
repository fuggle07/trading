import asyncio
from bot.sentiment_analyzer import SentimentAnalyzer
import os

sa = SentimentAnalyzer(project_id="utopian-calling-429014-r9")

async def test():
    try:
        res = await sa.model.generate_content_async("Hello")
        print("Success:", res.text)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
