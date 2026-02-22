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
    "sentiment_score": 0.35, # We know it was logged as 0.35
    "is_healthy": True,
    "health_reason": "test",
    "is_deep_healthy": True,
    "deep_health_reason": "test",
    "f_score": 8,
    "prediction_confidence": 0, # Ranker didn't score it (likely ran out of time or API limit)
    "is_low_exposure": False, # Exposure is no longer low!
    "band_width": 0.091, # We know it was logged as 9.1%
    "vix": 15.0,
    "volume": 0,
    "avg_volume": 1000000,
    "days_to_earnings": 10,
    "rsi": 50.0,
    "qty": 0.0,
    "holding_value": 0.0,
    "avg_price": 0.0,
    "hwm": 0.0
}

agent = SignalAgent(hurdle_rate=0.015, vol_threshold=0.35)
sig = agent.evaluate_strategy(market_data, force_eval=True, log_results=True)
print("FINAL REPRODUCTION 3:")
print(json.dumps(sig, indent=2))
