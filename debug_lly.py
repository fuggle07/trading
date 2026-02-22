from datetime import datetime
from bot.signal_agent import SignalAgent
import json
import logging

logging.basicConfig(level=logging.DEBUG)

market_data = {
    "ticker": "LLY",
    "current_price": 1009.52,
    "sma_20": 1000,
    "sma_50": 1000,
    "bb_upper": 1100,
    "bb_lower": 900,
    "sentiment_score": 0.40,
    "is_healthy": True,
    "health_reason": "test",
    "is_deep_healthy": True,
    "deep_health_reason": "test",
    "f_score": 8,
    "prediction_confidence": 85,
    "is_low_exposure": True,
    "band_width": 0.094,
    "vix": 15.0,
    "volume": 0,
    "avg_volume": 1000000,
    "days_to_earnings": 10,
    "rsi": 50.0,
    "qty": 0.0,
    "holding_value": 0.0,
    "avg_price": 0.0,
    "hwm": 0.0,
}

agent = SignalAgent(hurdle_rate=0.015, vol_threshold=0.35)
sig = agent.evaluate_strategy(market_data, force_eval=True, log_results=True)
print("FINAL REPRODUCTION:")
print(json.dumps(sig, indent=2))
