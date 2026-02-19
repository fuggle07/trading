import logging
from datetime import datetime, timezone
from typing import List, Dict
from google.cloud import bigquery
from bot.sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger("FeedbackAgent")


class FeedbackAgent:
    def __init__(self, project_id: str, bq_client: bigquery.Client):
        self.project_id = project_id
        self.bq_client = bq_client
        self.sentiment_analyzer = SentimentAnalyzer(project_id=project_id)
        self.rankings_table = f"{project_id}.trading_data.ticker_rankings"
        self.watchlist_table = f"{project_id}.trading_data.watchlist_logs"
        self.insights_table = f"{project_id}.trading_data.learning_insights"

    async def run_hindsight(self):
        """
        Analyzes past predictions vs. actual price movements.
        """
        logger.info("🧐 Starting Hindsight Analysis...")

        # 1. Get predictions from ~24h ago
        # 2. Get price movement since then
        # 3. Identify "Misses"
        # 4. Ask Gemini to critique

        misses = await self._find_misses()
        if not misses:
            logger.info(
                "✅ No significant misses found. Performance within expectations."
            )
            return

        for miss in misses:
            lesson = await self._critique_miss(miss)
            if lesson:
                self._log_insight_to_bq(miss["ticker"], lesson)

    async def _find_misses(self) -> List[Dict]:
        """Queries BQ to find cases where sentiment was wrong (Intraday hourly check)."""
        # We look for a prediction from ~1 hour ago (prediction_time)
        # And compare it to price NOW.
        # Strict logic:
        #   Snapshot A: 60-90 mins ago.
        #   Snapshot B: NOW (last 10 mins).
        query = f"""
        WITH predictions AS (
            SELECT ticker, sentiment_score as sentiment, price as start_price, timestamp,
                   ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
            FROM `{self.watchlist_table}`
            WHERE timestamp BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 MINUTE) 
                                AND TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 MINUTE)
        ),
        current_state AS (
            SELECT ticker, price as end_price,
                   ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
            FROM `{self.watchlist_table}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 15 MINUTE)
        )
        SELECT
            p.ticker,
            p.sentiment,
            p.start_price,
            c.end_price,
            ((c.end_price - p.start_price) / p.start_price) * 100 as pct_change
        FROM predictions p
        JOIN current_state c ON p.ticker = c.ticker
        WHERE p.rn = 1 AND c.rn = 1
        AND (
            (p.sentiment > 0.3 AND ((c.end_price - p.start_price) / p.start_price) < -0.005) -- Bullish but dropped > 0.5%
            OR 
            (p.sentiment < -0.3 AND ((c.end_price - p.start_price) / p.start_price) > 0.005) -- Bearish but rose > 0.5%
        )
        """
        try:
            query_job = self.bq_client.query(query)
            results = query_job.to_dataframe()
            return results.to_dict("records")
        except Exception as e:
            logger.error(f"❌ Failed to query misses: {e}")
            return []

    async def _critique_miss(self, miss: Dict) -> str:
        """Asks Gemini to analyze why its prediction was wrong."""
        ticker = miss["ticker"]
        sentiment = miss["sentiment"]
        pct_change = miss["pct_change"]

        prompt = f"""
        Hindsight Analysis for {ticker}:
        - Your Prediction: Sentiment {sentiment:.2f} ({"Bullish" if sentiment > 0 else "Bearish"})
        - Target Outcome: Price changed by {pct_change:.2f}%

        You were WRONG. The price moved in the opposite direction of your sentiment.

        Task:
        1. Hypothesize why you might have been wrong. (e.g., Did you ignore macro news? Was there a "sell the news" event? Is the stock decoupling from its headlines?)
        2. Provide a one-sentence "Lesson Learned" for your future self to avoid this specific trap.

        Format:
        LESSON: [one sentence lesson]
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
            if "LESSON:" in text:
                return text.split("LESSON:")[1].strip()
            return None
        except Exception as e:
            logger.error(f"[{ticker}] ⚠️ Hindsight Critique failed for {ticker}: {e}")
            return None

    def _log_insight_to_bq(self, ticker: str, lesson: str):
        """Saves the lesson to the learning_insights table."""
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "lesson": lesson,
            "category": "Intraday Adjustment",
        }
        try:
            self.bq_client.insert_rows_json(self.insights_table, [row])
            logger.info(f"[{ticker}] 💾 Logged lesson for {ticker}: {lesson}")
        except Exception as e:
            logger.error(f"[{ticker}] ❌ Failed to log insight for {ticker}: {e}")

    async def get_recent_lessons(self, limit=5) -> str:
        """Fetches top lessons to inject into prompts."""
        query = f"""
        SELECT ticker, lesson
        FROM `{self.insights_table}`
        ORDER BY timestamp DESC
        LIMIT {limit}
        """
        try:
            query_job = self.bq_client.query(query)
            results = query_job.to_dataframe()
            if results.empty:
                return ""

            summary = "\n".join(
                [f"- {row['ticker']}: {row['lesson']}" for _, row in results.iterrows()]
            )
            return f"\nHard-Learned Lessons from Past Misses:\n{summary}"
        except Exception as e:
            logger.error(f"⚠️ Failed to fetch lessons: {e}")
            return ""
