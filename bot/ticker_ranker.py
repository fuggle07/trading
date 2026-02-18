import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from google.cloud import bigquery
import finnhub
from sentiment_analyzer import SentimentAnalyzer
from feedback_agent import FeedbackAgent

logger = logging.getLogger("TickerRanker")


class TickerRanker:
 def __init__(self, project_id: str, bq_client: bigquery.Client):
 self.project_id = project_id
 self.bq_client = bq_client
 self.sentiment_analyzer = SentimentAnalyzer(project_id=project_id)
 self.finnhub_key = os.environ.get("EXCHANGE_API_KEY")
 self.finnhub_client = (
 finnhub.Client(api_key=self.finnhub_key) if self.finnhub_key else None
 )
 self.table_id = f"{project_id}.trading_data.ticker_rankings"
 self.feedback_agent = FeedbackAgent(project_id=project_id, bq_client=bq_client)

 async def fetch_overnight_news(self, ticker: str) -> List[Dict]:
 """Fetch news from the last 24 hours."""
 if not self.finnhub_client:
 return []

 now = datetime.now(timezone.utc)
 yesterday = now - timedelta(days=1)

 try:
 start_date = yesterday.strftime("%Y-%m-%d")
 end_date = now.strftime("%Y-%m-%d")

 client = self.finnhub_client
 if not client:
 return []

 news = await asyncio.wait_for(
 asyncio.to_thread(
 client.company_news, ticker, _from=start_date, to=end_date
 ),
 timeout=15,
 )

 if isinstance(news, str) and "limit reached" in news.lower():
 logger.warning(f"[{ticker}] ⚠️ Finnhub Rate Limit hit for {ticker}")
 return []

 return news
 except Exception as e:
 logger.error(f"[{ticker}] Error fetching news for {ticker}: {e}")
 return []

 async def analyze_ticker(self, ticker: str, lessons: str = "") -> Dict:
 """Analyze overnight news and get confidence score from Gemini."""
 news_list = list(await self.fetch_overnight_news(ticker))
 volume = len(news_list)

 if volume == 0:
 return {
 "ticker": ticker,
 "sentiment": 0.0,
 "confidence": 0,
 "reason": "No overnight news found.",
 }

 # Take top 10 headlines
 headlines = [str(n.get("headline", "")) for n in news_list[:10]]
 news_text = "\n".join(headlines)

 prompt = f"""
 Analyze the following overnight news headlines for {ticker}:
 {lessons}

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
 import asyncio

 response = await asyncio.wait_for(
 asyncio.to_thread(
 self.sentiment_analyzer.model.generate_content, prompt
 ),
 timeout=30,
 )
 text = response.text.strip()

 lines = text.split("\n")
 score = 0.0
 confidence = 0
 reason = "Failed to parse AI response."

 for line in lines:
 if line.startswith("SCORE:"):
 try:
 score = float(line.replace("SCORE:", "").strip())
 except:
 pass
 elif line.startswith("CONFIDENCE:"):
 try:
 confidence = int(line.replace("CONFIDENCE:", "").strip())
 except:
 pass
 elif line.startswith("REASON:"):
 reason = line.replace("REASON:", "").strip()

 return {
 "ticker": ticker,
 "sentiment": score,
 "confidence": confidence,
 "reason": reason,
 }
 except Exception as e:
 logger.error(f"[{ticker}] Error analyzing {ticker} with Vertex AI: {e}")
 return {
 "ticker": ticker,
 "sentiment": 0.0,
 "confidence": 0,
 "reason": "AI Analysis failed.",
 }

 def log_ranking_to_bq(self, results: List[Dict]):
 """Saves ranking results to BigQuery."""
 rows = []
 now = datetime.now(timezone.utc).isoformat()
 for res in results:
 rows.append(
 {
 "timestamp": now,
 "ticker": res["ticker"],
 "sentiment": res["sentiment"],
 "confidence": res["confidence"],
 "reason": res["reason"],
 }
 )

 if rows:
 errors = self.bq_client.insert_rows_json(self.table_id, rows)
 if errors:
 logger.error(f"BQ Insert Errors: {errors}")
 else:
 logger.info(f"Successfully logged {len(rows)} rankings to BQ.")

 async def rank_and_log(self, tickers: List[str]):
 """Rank tickers and log to BigQuery."""
 logger.info(f"Starting ticker ranking for {tickers}")

 # Fetch Hard-Learned Lessons
 lessons = await self.feedback_agent.get_recent_lessons(limit=3)
 if lessons:
 logger.info("🧠 Injecting lessons from memory into Gemini...")

 tasks = [self.analyze_ticker(t, lessons) for t in tickers]
 results = await asyncio.gather(*tasks)
 self.log_ranking_to_bq(results)
 return results
