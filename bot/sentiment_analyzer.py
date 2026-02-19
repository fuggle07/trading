import json
import vertexai
from vertexai.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold

from bot.telemetry import logger


class SentimentAnalyzer:
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.model = None
        self._init_vertex()

    def _init_vertex(self):
        try:
            vertexai.init(project=self.project_id, location=self.location)
            # Using Gemini 2.0 Flash for state-of-the-art speed and reasoning
            self.model = GenerativeModel("gemini-2.0-flash")
            logger.info("✨ Vertex AI (Gemini 2.0 Flash) initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Vertex AI: {e}")

    async def analyze_news(
        self, ticker: str, news_items: list, lessons: str = "", context: dict = None
    ) -> float:
        """
        Analyzes a list of news items and returns a sentiment score from -1.0 to 1.0.
        Returns 0.0 if analysis fails or no news provided.
        """
        if not self.model or not news_items:
            return 0.0

        # Limit to top 5 news items to fit context window efficiently and stay relevant
        top_news = news_items[:5]

        news_text = "\n\n".join(
            [
                f"- {item.get('headline', '')}: {item.get('summary', '')}"
                for item in top_news
            ]
        )

        context_text = ""
        if context:
            context_text = f"""
            Market-Wide Context: {context.get('macro', 'Stable')}
            Analyst Consensus: {context.get('analyst_consensus', 'Neutral')}
            Institutional Flow: {context.get('institutional_flow', 'Neutral')}
            """

        prompt = f"""
        You are a financial analysis expert powered by Gemini 2.0 Flash.
        Analyze the following data for the stock '{ticker}' to derive a high-conviction decision.

        {lessons}
        
        {context_text}

        News Data:
        {news_text if news_items else "No recent news found for this ticker."}

        Task:
        Determine the overall conviction score for this stock by synthesizing market context, analyst ratings, institutional flow, and news sentiment.
        Return a single JSON object with the following keys:
        - "score": A float between -1.0 (Strong Sell) and 1.0 (Strong Buy).
        - "reasoning": A brief explanation citing specific data points (e.g., "$QQQ strength" or "analyst upgrades").

        Output JSON only. Do not include markdown formatting.
        """

        try:
            # Safety settings to avoid blocking financial discussions
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }

            import asyncio

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    safety_settings=safety_settings,
                    generation_config={"response_mime_type": "application/json"},
                ),
                timeout=30,
            )

            result_text = response.text.strip()
            # Clean up potential markdown code blocks if the model ignores instruction
            if result_text.startswith("```json"):
                result_text = result_text[7:-3]
            elif result_text.startswith("```"):
                result_text = result_text[3:-3]

            data = json.loads(result_text)
            score = float(data.get("score", 0.0))
            reasoning = data.get("reasoning", "No reasoning provided.")

            logger.info(
                f"[{ticker}] 🧠 Gemini Analysis: Score={score} | Reason: {reasoning}"
            )
            return score

        except Exception as e:
            logger.error(f"[{ticker}] ⚠️ Gemini Analysis Failed: {e}")
            return 0.0
