import os
import asyncio
import subprocess
from google.cloud import bigquery
from bot.ticker_ranker import TickerRanker

async def main():
    # 1. Configuration
    project_id = "utopian-calling-429014-r9"
    tickers = ["TSLA", "NVDA", "AMD", "PLTR", "COIN", "META", "GOOG", "MSFT", "GOLD", "NEM", "AMZN", "AVGO", "CRM", "ORCL", "LMT", "MU"]

    print(f"🚀 Initializing Ticker Ranker for Project: {project_id}")

    # 2. Fetch Secrets from GCP
    def get_secret(name):
        try:
            val = subprocess.check_output(
                ["gcloud", "secrets", "versions", "access", "latest", f"--secret={name}"],
                stderr=subprocess.STDOUT
            ).decode("utf-8").strip()
            return val
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch secret {name}: {e}")
            return None

    # TickerRanker expects EXCHANGE_API_KEY
    finnhub_key = get_secret("FINNHUB_KEY")
    if finnhub_key:
        os.environ["EXCHANGE_API_KEY"] = finnhub_key
    
    # 3. Initialize Ranker
    bq_client = bigquery.Client(project=project_id)
    ranker = TickerRanker(project_id, bq_client)

    # 4. Run Ranking
    print(f"📊 Running overnight news analysis for tickers: {tickers}")
    try:
        results = await ranker.rank_and_log(tickers)
        print("\n✅ Ranking Complete!")
        print("-" * 40)
        for res in results:
            sentiment = res.get('sentiment', 0.0)
            conf = res.get('confidence', 0)
            indicator = "🟢" if sentiment > 0.3 and conf > 70 else "🔴" if sentiment < -0.3 else "⚪"
            print(f"[{res['ticker']}] {indicator} Sent: {sentiment:>5.2f} | Conf: {conf:>3} | {res['reason']}")
        print("-" * 40)
    except Exception as e:
        print(f"❌ Error during ranking: {e}")

if __name__ == "__main__":
    asyncio.run(main())
