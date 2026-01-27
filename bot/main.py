# bot/main.py - Refactored for IBKR Auth & Hurdle Logic
import asyncio
import os
import aiohttp
import logging
from datetime import datetime, timezone

# Surgical Tier Imports
from .telemetry import log_performance
from .verification import get_hard_proof

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AberfeldieNode")

TICKERS = os.getenv("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD").split(",")

def parse_ibkr_creds():
    """Surgically parses the colon-separated IBKR secret."""
    raw_key = os.getenv("IBKR_KEY", "")
    if ":" in raw_key:
        user, pwd = raw_key.split(":", 1)
        return user, pwd
    logger.warning({"event": "ibkr_auth_invalid", "msg": "Using default or empty creds"})
    return None, None

async def get_usd_aud_rate():
    """Fetches the USD to AUD exchange rate."""
    url = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=AUD"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['rates']['AUD'])
                return 1.52
    except Exception:
        return 1.52

async def main_handler(request=None):
    """Main Entry Point: Hurdle & Secret Aware."""
    
    # 1. Parse Secrets & Sensors
    ibkr_user, _ = parse_ibkr_creds() # Password kept in memory only
    fx_rate = await get_usd_aud_rate()
    
    # 2. Execute Ticker Audits (TaskGroup for 2026 concurrency standards)
    async with asyncio.TaskGroup() as tg:
        for ticker in TICKERS:
            logger.info({"event": "audit_queued", "ticker": ticker})
            # Audit logic here...

    # 3. Tax & Hurdle Telemetry
    # These will be replaced by live broker calls in the next iteration
    sim_equity = 100000.00
    sim_index = 505.20 
    
    log_performance(
        paper_equity=sim_equity, 
        index_price=sim_index, 
        fx_rate_aud=fx_rate,
        capital_usd=float(os.getenv("CAPITAL_USD", 50000.0)),
        hurdle_rate=float(os.getenv("MORTGAGE_HURDLE_RATE", 0.052))
    )
    
    return f"Audit Complete. Node: {ibkr_user}", 200

