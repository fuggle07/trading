# bot/main.py - Concurrent Nasdaq Orchestrator
import os
import asyncio
import vertexai
from vertexai.generative_models import GenerativeModel
from .verification import get_hard_proof  # Relative import
from .liquidate import emergency_liquidate_all  # Relative import

# --- 1. GLOBAL CONFIG & RATE LIMITS ---
TIER = os.getenv("FINNHUB_TIER", "FREE")
GATEKEEPER = asyncio.Semaphore(30 if TIER == "FREE" else 100)
TICKERS = [t.strip() for t in os.getenv("BASE_TICKERS", "QQQ,NVDA").split(",")]

# AI Setup
PROJECT_ID = os.getenv("PROJECT_ID")
if PROJECT_ID:
    vertexai.init(project=PROJECT_ID, location="us-central1")
    AGENT = GenerativeModel("gemini-1.5-pro")

async def run_audit(ticker):
    """Surgical Audit with integrated Emergency Exit capability."""
    async with GATEKEEPER:
        print(f"📡 Auditing {ticker}...")
        
        # MSV Verification
        score = await asyncio.to_thread(get_hard_proof, ticker)
        
        # AI Reasoning
        prompt = f"Audit {ticker}. Proof Score: {score}. Respond with GO, NO-GO, or EMERGENCY_EXIT."
        response = await AGENT.generate_content_async(prompt)
        decision = response.text.upper()

        if "EMERGENCY_EXIT" in decision:
            print(f"🛑 [SIGNAL] {ticker} triggered EMERGENCY_EXIT. Shutting down...")
            await emergency_liquidate_all()
            return

        if "GO" in decision and score > 0:
            print(f"✅ {ticker} AUTHORIZED.")
            # execute_trade_router(ticker) call here
        else:
            print(f"❌ {ticker} REJECTED.")

async def main_handler(request=None):
    """Main Entry Point for Cloud Functions."""
    print(f"🚀 Initializing Audit Loop for: {TICKERS}")
    # Run all audits concurrently
    await asyncio.gather(*(run_audit(t) for t in TICKERS))
    return "Audit Complete", 200

if __name__ == "__main__":
    asyncio.run(main_handler())

