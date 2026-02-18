from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime
import pytz
from telemetry import log_decision


class SignalAgent:
 """
 The decision-making engine with built-in Volatility Filtering and Holiday Awareness.
 """

 def __init__(
 self,
 risk_profile: float = 0.02,
 vol_threshold: float = 0.25,
 hurdle_rate: float = 0.015,
 ):
 self.risk_per_trade = Decimal(str(risk_profile))
 # vol_threshold: 0.05 means if the bands are > 5% apart, we don't trade.
 self.vol_threshold = Decimal(str(vol_threshold))
 self.hurdle_rate = Decimal(str(hurdle_rate))

 # 2026 US NASDAQ Holidays
 self.market_holidays = [
 "2026-01-01", # New Year's Day
 "2026-01-19", # Martin Luther King, Jr. Day
 "2026-02-16", # Washington's Birthday (Presidents' Day)
 "2026-04-03", # Good Friday
 "2026-05-25", # Memorial Day
 "2026-06-19", # Juneteenth
 "2026-07-03", # Independence Day (Observed)
 "2026-09-07", # Labor Day
 "2026-11-26", # Thanksgiving Day
 "2026-12-25", # Christmas Day
 ]

 def is_market_open(self):
 """
 Determines if the US stock market is currently open.
 Checks: Weekends, Holidays, and Trading Hours (9:30 AM - 4:00 PM ET).
 """
 ny_tz = pytz.timezone("America/New_York")
 now = datetime.now(ny_tz)

 # 1. Weekend Check (Saturday=5, Sunday=6)
 if now.weekday() >= 5:
 return False

 # 2. Holiday Check
 today_str = now.strftime("%Y-%m-%d")
 if today_str in self.market_holidays:
 return False

 # 3. Market Hours (9:30 AM - 4:00 PM ET)
 current_time = now.time()
 market_open = now.replace(hour=9, minute=30, second=0, microsecond=0).time()
 market_close = now.replace(hour=16, minute=0, second=0, microsecond=0).time()

 if current_time < market_open or current_time >= market_close:
 return False

 return True

 def evaluate_strategy(
 self, market_data: Dict, force_eval: bool = False
 ) -> Optional[Dict]:
 """
 Evaluates signals only if the market is open and volatility is within safe bounds.
 Can be forced to evaluate (Dry-Run) even if market is closed.
 """
 ticker = market_data.get("ticker", "Unknown")

 # 1. Market Status Filter
 if not force_eval and not self.is_market_open():
 log_decision(
 ticker, "SKIP", "Market is closed (Weekend, Holiday, or After-Hours)"
 )
 return None

 # 2. Volatility Filter (The Gatekeeper)
 is_stable, vol_pct = self._check_volatility(market_data)
 if not is_stable:
 log_decision(
 ticker,
 "SKIP",
 f"Volatility too high ({vol_pct:.2%})",
 {"vol_pct": float(vol_pct)},
 )
 return None

 # 3. Strategy Logic (SMA Crossover)
 price = Decimal(str(market_data["current_price"]))
 sma_short = Decimal(str(market_data["sma_20"]))
 sma_long = Decimal(str(market_data["sma_50"]))

 signal = None
 if sma_short > sma_long:
 signal = {
 "action": "BUY",
 "price": price,
 "reason": "SMA_CROSSOVER_BULLISH",
 }
 elif sma_short < sma_long:
 signal = {
 "action": "SELL",
 "price": price,
 "reason": "SMA_CROSSOVER_BEARISH",
 }
 else:
 log_decision(ticker, "SKIP", "No Technical Signal (SMA)")
 return None

 # 3b. Stop Loss Override (Safety Net)
 # If we own it (implied by having an avg_price > 0) and price is down 10%
 avg_price = Decimal(str(market_data.get("avg_price", 0.0)))
 if avg_price > 0:
 stop_price = avg_price * Decimal("0.90")
 if price < stop_price:
 log_decision(
 ticker,
 "SELL",
 f"STOP LOSS TRIGGERED: Price {price} < {stop_price} (Avg: {avg_price})",
 )
 signal = {"action": "SELL", "price": price, "reason": "STOP_LOSS_HIT"}

 # 3c. Sentiment Exit Override (The Black Swan Exit)
 # If sentiment is catastrophically negative (< -0.6), we exit immediately.
 sentiment = market_data.get("sentiment_score")
 if sentiment is not None:
 sentiment_dec = Decimal(str(sentiment))
 if sentiment_dec < Decimal("-0.6"):
 log_decision(
 ticker,
 "SELL",
 f"EXTREME BEARISH SENTIMENT: {sentiment_dec} < -0.6. Forcing EXIT.",
 )
 signal = {
 "action": "SELL",
 "price": price,
 "reason": "EXTREME_BEARISH_SENTIMENT",
 }

 # 4. Sentiment Filter (The Vibe Check) - Apply ONLY to BUYs
 # We want to be able to SELL even if sentiment is terrible (especially then!)
 if signal and signal["action"] == "BUY":
 sentiment = market_data.get("sentiment_score")
 # User Optimized Sentiment Threshold:
 # - Conviction Mode: 0.2 (Exposure >= 25%)
 # - Seeding Mode: 0.0 (Exposure < 25%)
 is_low_exposure = market_data.get("is_low_exposure", False)
 sentiment_floor = Decimal("0.0") if is_low_exposure else Decimal("0.2")

 if sentiment is not None:
 sentiment_dec = Decimal(str(sentiment))
 if sentiment_dec < sentiment_floor:
 log_decision(
 ticker,
 "SKIP",
 f"Sentiment ({sentiment_dec:.2f}) < Hurdle-Adjusted Floor ({sentiment_floor:.2f})",
 )
 return None

 # 5. Fundamental Filter (The Value Check) - Apply ONLY to BUYs
 if signal and signal["action"] == "BUY":
 is_healthy = market_data.get(
 "is_healthy", True
 ) # Default to True if missing
 reason = market_data.get("health_reason", "Unknown")

 if not is_healthy:
 log_decision(
 ticker, "SKIP", f"Fundamental Health Check Failed ({reason})"
 )
 return None

 # 6. Deep Filing Filter (The Solvency Check) - Apply ONLY to BUYs
 if signal and signal["action"] == "BUY":
 is_deep_healthy = market_data.get("is_deep_healthy", True)
 deep_reason = market_data.get("deep_health_reason", "Unknown")

 if not is_deep_healthy:
 log_decision(
 ticker, "SKIP", f"Deep Filing Analysis Failed ({deep_reason})"
 )
 return None

 # 6. Prediction Confidence Filter (The Morning Conviction Check) - Apply to BUYs and SELLs
 # Safety: We NEVER suppress a STOP_LOSS_HIT exit.
 if (
 signal
 and signal["action"] in ["BUY", "SELL"]
 and signal.get("reason") != "STOP_LOSS_HIT"
 ):
 confidence = market_data.get("prediction_confidence")
 if confidence is not None:
 confidence_val = int(confidence)
 if confidence_val < 65:
 log_decision(
 ticker,
 "SKIP",
 f"{signal['action']} Rejected: Confidence ({confidence_val}%) < Morning Threshold (65%)",
 )
 return None
 else:
 # If no confidence is found (e.g. ranking job failed), we default to allowed
 print(
 f"[{market_data.get('ticker')}] ⚠️ Warning: No prediction confidence found. Proceeding without filter."
 )

 # No-op: main.py handles the coordination of conviction swaps,
 # but we acknowledge it here for consistency in signal reasons.
 return signal

 def _check_volatility(self, market_data: Dict) -> tuple[bool, Decimal]:
 """
 Calculates the width of Bollinger Bands relative to the price.
 Returns (is_stable, current_volatility_percentage).
 """
 upper_band = Decimal(str(market_data["bb_upper"]))
 lower_band = Decimal(str(market_data["bb_lower"]))
 current_price = Decimal(str(market_data["current_price"]))

 # Calculate band width as a percentage of price
 vol_pct = (upper_band - lower_band) / current_price

 # If the gap is too wide, the 'edge' is lost in the noise
 return (vol_pct <= self.vol_threshold, vol_pct)
