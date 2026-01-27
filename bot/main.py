# bot/main.py - Version 2.5 (The Unified Aberfeldie Agent)
import asyncio
import os
import aiohttp
import vertexai
from vertexai.generative_models import GenerativeModel

# Surgical Tiers: Relative imports from your /bot directory
from .telemetry import log_performance
from .verification import get_hard_proof
from .liquidate import emergency_liquidate_all

# Logistics: Global Nasdaq Watchlist
TICKERS = os.getenv("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD").split(",")

# --- VOLATILITY SENSORS ---

async def get_current_vix():
    """
    Surgically fetches the VIX from Finnhub to gauge market fear.
    Returns 20.0 (Baseline) if the sensor fails to prevent a crash.
    """
    api_key = os.getenv("FINNHUB_KEY")
    url = f"https://finnhub.io/api/v1/quote?symbol=^VIX&token={api_key}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    # 'c' is the current price in Finnhub's schema
                    return float(data.get('c', 20.0))
                return 20.0
    except Exception as e:
        print(f"⚠️ VIX Sensor Offline: {e}")
        return 20.0

def calculate_risk_multiplier(vix):
    """
    Scales risk based on env.yaml thresholds.
    High VIX = Smaller positions to preserve capital.
    """
    high_gate = float(os.getenv("VIX_THRESHOLD_HIGH", 30.0))
    sensitivity = float(os.getenv("VOLATILITY_SENSITIVITY", 1.0))
    
    if vix >= high_gate:
        # Reduces risk by half in panic regimes, adjusted by sensitivity
        # Formula: 0.5 ^ sensitivity (e.g., if sens=1, multiplier is 0.5)
        return 0.5 ** sensitivity
    return 1.0

# --- AUDIT EXECUTION ---

async def run_audit(ticker, multiplier):
    """Placeholder for the core audit logic per ticker."""
    print(f"🔍 [AUDIT] Analyzing {ticker} with {multiplier}x Risk scaling...")
    # This would call agent.py and verification.py logic
    await asyncio.sleep(0.1) 

# --- MASTER HANDLER ---

async def main_handler(request=None):
    """Main Entry Point for Cloud Functions (GCP 2nd Gen)."""
    print(f"🚀 Initializing Audit Loop for: {TICKERS}")
    
    # 1. Detect Market Regime
    vix_value = await get_current_vix()
    risk_multiplier = calculate_risk_multiplier(vix_value)
    print(f"📊 Market Regime: VIX {vix_value} | Risk Scaling: {risk_multiplier}x")
     
    # 2. Run all audits concurrently across your watchlist
    # Passing the risk_multiplier to ensure sized entries
    await asyncio.gather(*(run_audit(t, risk_multiplier) for t in TICKERS))
     
    # 3. Performance Telemetry (The Looker Studio Feed)
    # Stage 1: Simulated benchmarks for initial dashboard verification
    simulated_equity = 100000.00
    simulated_index = 505.20 # e.g., current QQQ price
    
    print("📈 Finalizing Audit Cycle & Syncing Telemetry...")
    log_performance(simulated_equity, simulated_index)
    
    return f"Audit Complete. VIX: {vix_value}, Multiplier: {risk_multiplier}", 200

