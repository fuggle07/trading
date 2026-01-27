import asyncio
import os
import aiohttp
import logging
from datetime import datetime, timezone

# Surgical Tier Imports
from .telemetry import log_performance
from .verification import get_hard_proof
from .liquidate import emergency_liquidate_all

# Configure Structured Logging for GCP Logs Explorer
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AberfeldieNode")

TICKERS = os.getenv("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD").split(",")

async def get_current_vix():
    """Surgically fetches VIX with a 5s strict timeout."""
    api_key = os.getenv("FINNHUB_KEY")
    url = f"https://finnhub.io/api/v1/quote?symbol=^VIX&token={api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                data = await response.json()
                return float(data.get('c', 20.0))
    except Exception as e:
        logger.error({"event": "vix_sensor_fail", "error": str(e)})
        return 20.0

def calculate_risk_multiplier(vix):
    high_gate = float(os.getenv("VIX_THRESHOLD_HIGH", 30.0))
    sensitivity = float(os.getenv("VOLATILITY_SENSITIVITY", 1.0))
    return 0.5 ** sensitivity if vix >= high_gate else 1.0

async def run_audit(ticker, multiplier):
    """Refactored audit logic with structured telemetry."""
    # This is where the Agent.py reasoning would be triggered
    logger.info({"event": "audit_start", "ticker": ticker, "multiplier": multiplier})
    await asyncio.sleep(0.1) # Simulated I/O
    return f"{ticker}_SUCCESS"

async def main_handler(request=None):
    """Main Entry Point: Now Tax & Regime Aware."""
    
    # 1. Poll Sensors (Concurrent execution for speed)
    vix_task = get_current_vix()
    fx_task = get_usd_aud_rate()
    vix_value, fx_rate = await asyncio.gather(vix_task, fx_task)
    
    risk_multiplier = calculate_risk_multiplier(vix_value)
    
    # 2. Execute Ticker Audits
    async with asyncio.TaskGroup() as tg:
        for ticker in TICKERS:
            tg.create_task(run_audit(ticker, risk_multiplier))
     
    # 3. Tax-Aware Telemetry
    # Stage 2 will replace these with live broker balance calls
    sim_equity = 100000.00
    sim_index = 505.20 
    
    log_performance(
        paper_equity=sim_equity, 
        index_price=sim_index, 
        fx_rate_aud=fx_rate,  # <--- No longer hardcoded
        brokerage=0.0         # Adjusted per trade logic
    )
    
    return f"Audit Complete. FX: {fx_rate}, VIX: {vix_value}", 200

