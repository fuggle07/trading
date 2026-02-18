#!/usr/bin/env python3
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict

# Reuse existing agents
from bot.sentiment_analyzer import SentimentAnalyzer
import finnhub

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TickerRanker")

# Configuration
TICKERS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMD"]
FINNHUB_KEY = os.environ.get("FINNHUB_KEY")
PROJECT_ID = os.environ.get("PROJECT_ID", "aberfeldie-node") # Default or from env

class TickerRanker:
 def __init__(self):
 self.sentiment_analyzer = SentimentAnalyzer(project_id=PROJECT_ID)
 self.finnhub_client = (
 finnhub.Client(api_key=FINNHUB_KEY) if FINNHUB_KEY else None
 )

 async def fetch_overnight_news(self, ticker: str) -> List[Dict]:
 """Fetch news from the last 24 hours."""
 if not self.finnhub_client:
 return []

 now = datetime.now(timezone.utc)
 yesterday = now - timedelta(days=1)

 try:
 start_date = yesterday.strftime("%Y-%m-%d")
 end_date = now.strftime("%Y-%m-%d")

 news = await asyncio.to_thread(
 self.finnhub_client.company_news, ticker, _from=start_date, to=end_date
 )

 # Direct check for rate limit string if returned by library
 if isinstance(news, str) and "limit reached" in news.lower():
 logger.warning(f"⚠️ Finnhub Rate Limit hit for {ticker}")
 return []

 return news
 except Exception as e:
 if "429" in str(e):
 logger.warning(f"⚠️ Rate Limit (429) for {ticker}")
 else:
 logger.error(f"Error fetching news for {ticker}: {e}")
 return []

 async def analyze_ticker(self, ticker: str) -> Dict:
 """Analyze overnight news and get confidence score from Gemini."""
 news = await self.fetch_overnight_news(ticker)
 volume = len(news)

 if volume == 0:
 return {
 "ticker": ticker,
 "volume": 0,
 "sentiment": 0.0,
 "confidence": 0,
 "reason": "No overnight news found.",
 }

 # Extract headlines
 headlines = [
 n.get("headline", "") for n in news[:10]
 ] # Limit to 10 for context
 news_text = "\n".join(headlines)

 # Prompt Gemini for confidence
 # We'll use a specific prompt to get structured data
 prompt = f"""
 Analyze the following overnight news headlines for {ticker}:

 {news_text}

 Provide:
 1. Aggregate Sentiment Score (-1.0 to 1.0).
 2. Prediction Confidence Score (0 to 100): How clearly these headlines suggest a price movement (up or down).
 3. A brief one-sentence reason.

 Format your response exactly as:
 SCORE: [score]
 CONFIDENCE: [confidence]
 REASON: [reason]
 """

 try:
 # We bypass the standard evaluate_news to get custom structured output
 response = self.sentiment_analyzer.model.generate_content(prompt)
 text = response.text.strip()

 # Parse response
 lines = text.split("\n")
 score = 0.0
 confidence = 0
 reason = "Failed to parse AI response."

 for line in lines:
 if line.startswith("SCORE:"):
 score = float(line.replace("SCORE:", "").strip())
 elif line.startswith("CONFIDENCE:"):
 confidence = int(line.replace("CONFIDENCE:", "").strip())
 elif line.startswith("REASON:"):
 reason = line.replace("REASON:", "").strip()

 return {
 "ticker": ticker,
 "volume": volume,
 "sentiment": score,
 "confidence": confidence,
 "reason": reason,
 }
 except Exception as e:
 logger.error(f"Error analyzing {ticker} with Vertex AI: {e}")
 return {
 "ticker": ticker,
 "volume": volume,
 "sentiment": 0.0,
 "confidence": 0,
 "reason": "AI Analysis failed.",
 }

 async def rank_all_tickers(self):
 """Rank all tickers and output top 3."""
 logger.info(
 f"--- Morning Ticker Ranking ({datetime.now().strftime('%Y-%m-%d')}) ---"
 )

 tasks = [self.analyze_ticker(t) for t in TICKERS]
 results = await asyncio.gather(*tasks)

 # Filter out tickers with no news if possible, otherwise keep them
 # Sort primarily by Confidence, then by Volume
 ranked = sorted(
 results, key=lambda x: (x["confidence"], x["volume"]), reverse=True
 )

 top_3 = ranked[:3]

 print("\n## 🚀 Top 3 Tickers to Watch Today\n")
 print("| Rank | Ticker | Confidence | Sentiment | Vol | Reason |")
 print("|------|--------|------------|-----------|-----|--------|")
 for i, res in enumerate(top_3, 1):
 sent_icon = (
 "📈" if res["sentiment"] > 0 else "📉" if res["sentiment"] < 0 else "😐"
 )
 print(
 f"| {i} | **{res['ticker']}** | {res['confidence']}% | {sent_icon} {res['sentiment']:.2f} | {res['volume']} | {res['reason']} |"
 )
 print("\n")

async def main():
 ranker = TickerRanker()
 await ranker.rank_all_tickers()

if __name__ == "__main__":
 asyncio.run(main())
