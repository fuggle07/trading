import asyncio
import os
import logging
import aiohttp
import pandas as pd
from datetime import datetime, timezone
from flask import Flask, jsonify
from signal_agent import SignalAgent
from execution_manager import ExecutionManager

# 1. Initialize App & Components
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AberfeldieNode")

# Load configuration from Environment
TICKERS = os.getenv("BASE_TICKERS", "NVDA,AAPL,TSLA,MSFT,AMD").split(",")
PORT = int(os.environ.get("PORT", 8080))

# Initialize our custom modules
agent = SignalAgent(risk_profile=0.02, vol_threshold=0.05)
executor = ExecutionManager()

# --- HELPER LOGIC ---

async def fetch_market_data(ticker: str) -> dict:
    """
    SENSE: Fetches historical and current price data.
    Note: For a real edge, replace this with a professional API (Polygon, Alpaca, etc.)
    """
    # Simulated fetching of the last 50 periods of data for SMA/BB calculation
    # In production, you would fetch this from an exchange API
    url = f"https://api.example.com/v1/ohlcv/{ticker}?limit=50"
    
    # Placeholder: Generating mock data for the structure
    # Real logic would use: async with session.get(url) ...
    prices = [150.0 + i for i in range(50)] # Mock price trend
    df = pd.DataFrame(prices, columns=['close'])
    
    # Calculate Indicators
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['std_20'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['sma_20'] + (df['std_20'] * 2)
    df['bb_lower'] = df['sma_20'] - (df['std_20'] * 2)
    
    latest = df.iloc[-1]
    return {
        "ticker": ticker,
        "current_price": latest['close'],
        "sma_20": latest['sma_20'],
        "sma_50": latest['sma_50'],
        "bb_upper": latest['bb_upper'],
        "bb_lower": latest['bb_lower']
    }

# --- CORE TRADING HANDLER ---

async def audit_and_trade(ticker: str):
    """The full cycle for a single ticker."""
    try:
        # 1. SENSE
        market_data = await fetch_market_data(ticker)
        logger.info(f"Sensed {ticker}: Price {market_data['current_price']}")

        # 2. THINK
        signal = agent.evaluate_strategy(market_data)

        # 3. ACT
        if signal:
            signal['ticker'] = ticker # Add context for executor
            result = executor.place_order(signal)
            logger.info(f"Execution Result for {ticker}: {result['status']}")
        else:
            logger.info(f"No valid signal/Stable volatility for {ticker}")

    except Exception as e:
        logger.error(f"Failed audit for {ticker}: {str(e)}")

async def main_handler() -> tuple[str, int]:
    """Orchestrates the audit across all tickers concurrently."""
    async with asyncio.TaskGroup() as tg:
        for ticker in TICKERS:
            tg.create_task(audit_and_trade(ticker))
    
    return f"Audit and Trade cycle complete for {len(TICKERS)} tickers.", 200

# --- CLOUD RUN ROUTES ---

@app.route('/health', methods=['GET'], strict_slashes=False)
def health():
    return jsonify({
        "status": "healthy",
        "node": "Aberfeldie",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/run-audit', methods=['POST'], strict_slashes=False)
def run_audit_endpoint():
    try:
        # Bridges Flask (Sync) to the Async logic
        result = asyncio.run(main_handler())
        result_msg, status_code = result
        return jsonify({"message": result_msg}), status_code
    except Exception as e:
        logger.error({"event": "audit_crash", "error": str(e)})
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
