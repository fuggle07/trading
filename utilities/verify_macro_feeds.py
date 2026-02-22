import asyncio
import os
from bot.fundamental_agent import FundamentalAgent
from bot.telemetry import logger
import logging

# Set logging to info
logging.basicConfig(level=logging.INFO)


async def verify_macro_feeds():
    print(
        "🚀 Verifying Macro Intelligence Feeds (with Finnhub Fallback & GCP Secrets)..."
    )

    # Attempt to fetch secrets from environment or GCP
    fmp_key = os.getenv("FMP_KEY")
    finnhub_key = os.getenv("FINNHUB_KEY") or os.getenv("EXCHANGE_API_KEY")
    av_key = os.getenv("ALPHA_VANTAGE_KEY")

    if not (fmp_key and finnhub_key and av_key):
        print("🔗 Fetching secrets from GCP Secret Manager...")
        try:
            import subprocess

            def get_secret(name):
                cmd = f"gcloud secrets versions access latest --secret='{name}'"
                return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()

            if not fmp_key:
                fmp_key = get_secret("FMP_KEY")
            if not finnhub_key:
                finnhub_key = get_secret("FINNHUB_KEY")
            if not av_key:
                av_key = get_secret("ALPHA_VANTAGE_KEY")

            os.environ["FMP_KEY"] = fmp_key
            os.environ["FINNHUB_KEY"] = finnhub_key
            os.environ["ALPHA_VANTAGE_KEY"] = av_key
            print("✅ Secrets synchronized.")
        except Exception as e:
            print(f"⚠️ Failed to fetch secrets from GCP: {e}")

    # Initialize Finnhub
    import finnhub

    finnhub_client = finnhub.Client(api_key=finnhub_key)

    agent = FundamentalAgent(finnhub_client=finnhub_client)

    # 1. Test Economic Calendar
    print("\n--- Economic Calendar ---")
    calendar = await agent.get_economic_calendar()
    if calendar:
        for ev in calendar:
            print(
                f"📅 {ev.get('date')} | {ev.get('event')} | Impact: {ev.get('impact')}"
            )
    else:
        print("❌ No calendar data found (Check FMP_KEY)")

    # 2. Test Treasury Rates
    print("\n--- Treasury Rates ---")
    rates = await agent.get_treasury_rates()
    if rates:
        print(
            f"📈 10Y Yield: {rates.get('10Y')}% | 2Y Yield: {rates.get('2Y')}% (Date: {rates.get('date')})"
        )
    else:
        print("❌ No treasury data found")

    # 3. Test Market Indices (VIX/SPY/QQQ)
    print("\n--- Market Indices ---")
    indices = await agent.get_market_indices()
    if indices:
        print(
            f"📉 VIX: {indices.get('vix')} | SPY: {indices.get('spy_perf')}% | QQQ: {indices.get('qqq_perf')}%"
        )
    else:
        print("❌ No indices data found")


if __name__ == "__main__":
    if not os.getenv("FMP_KEY"):
        print("⚠️  FMP_KEY environment variable is missing!")
    else:
        asyncio.run(verify_macro_feeds())
