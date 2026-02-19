from decimal import Decimal
from typing import Dict
from datetime import datetime
import pytz
from bot.telemetry import log_decision


class SignalAgent:
    """
    The decision-making engine with built-in Volatility Filtering and Holiday Awareness.
    """

    def __init__(
        self,
        risk_profile: float = 0.02,
        vol_threshold: float = 0.35,
        hurdle_rate: float = 0.015,
    ):
        self.risk_per_trade = Decimal(str(risk_profile))
        # vol_threshold: 0.05 means if the bands are > 5% apart, we don't trade.
        self.vol_threshold = Decimal(str(vol_threshold))
        self.hurdle_rate = Decimal(str(hurdle_rate))

        # 2026 US NASDAQ Holidays
        self.market_holidays = [
            "2026-01-01",  # New Year's Day
            "2026-01-19",  # Martin Luther King, Jr. Day
            "2026-02-16",  # Washington's Birthday (Presidents' Day)
            "2026-04-03",  # Good Friday
            "2026-05-25",  # Memorial Day
            "2026-06-19",  # Juneteenth
            "2026-07-03",  # Independence Day (Observed)
            "2026-09-07",  # Labor Day
            "2026-11-26",  # Thanksgiving Day
            "2026-12-25",  # Christmas Day
        ]

    def is_market_open(self):
        """
        Determines if the US stock market is currently open.
        """
        # Get current time in New York
        ny_tz = pytz.timezone("America/New_York")
        now = datetime.now(ny_tz)

        # 1. Weekend Check
        if now.weekday() >= 5:
            return False

        # 2. Holiday Check
        date_str = now.strftime("%Y-%m-%d")
        if date_str in self.market_holidays:
            return False

        # 3. Time Check (9:30 AM - 4:00 PM)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        if market_open <= now <= market_close:
            return True

        return False

    def evaluate_bands(self, current_price: float, upper: float, lower: float) -> str:
        """
        Calculates signal based on Bollinger Bands.
        Includes a Volatility Filter (vol_threshold).
        """
        price = Decimal(str(current_price))
        up = Decimal(str(upper))
        lo = Decimal(str(lower))

        # Calculate Band Width % (Volatility Filter)
        band_width = (up - lo) / price
        if band_width > self.vol_threshold:
            return "VOLATILE_IGNORE"

        if price >= up:
            return "SELL"
        elif price <= lo:
            return "BUY"

        return "HOLD"

    def evaluate_strategy(
        self,
        market_data: Dict,
        force_eval: bool = False,
    ) -> Dict:
        """
        Orchestrates Signal Selection by combining technicals, sentiment, and fundamental conviction.
        """
        ticker = market_data.get("ticker", "Unknown")
        current_price = market_data.get("current_price", 0.0)
        indicators = {
            "upper": market_data.get("bb_upper", 0.0),
            "lower": market_data.get("bb_lower", 0.0),
            "sma_20": market_data.get("sma_20", 0.0),
            "sma_50": market_data.get("sma_50", 0.0),
        }
        sentiment = market_data.get("sentiment_score", 0.0)
        fundamentals = {
            "is_healthy": market_data.get("is_healthy", True),
            "health_reason": market_data.get("health_reason", ""),
            "is_deep_healthy": market_data.get("is_deep_healthy", True),
            "deep_health_reason": market_data.get("deep_health_reason", ""),
            "f_score": market_data.get("f_score", 0),  # Piotroski F-Score
            "score": market_data.get("prediction_confidence", 0),
        }
        avg_price = market_data.get("avg_price", 0.0)
        is_low_exposure = market_data.get("is_low_exposure", False)
        rsi = float(market_data.get("rsi", 50.0))
        lessons = ""  # Placeholder for now

        technical_signal = self.evaluate_bands(
            current_price, indicators.get("upper", 0), indicators.get("lower", 0)
        )

        # Logic for Final Decision
        final_action = "IDLE"
        conviction = 0
        sentiment_gate = 0.4  # Slightly biased towards caution

        # 1. Technical Baseline
        if technical_signal == "BUY" and sentiment >= sentiment_gate:
            final_action = "BUY"
            conviction = 60 + int(sentiment * 40)  # [60 - 100]
        elif technical_signal == "SELL":
            final_action = "SELL"
            conviction = 80
        elif technical_signal == "VOLATILE_IGNORE":
            final_action = "IDLE"
            conviction = 0
        else:
            final_action = "IDLE"
            # ENHANCEMENT: Low Exposure Aggression
            # If we are in cash, we don't wait for price to hit the bottom band
            # if the narrative (sentiment) and health (fundamentals) are solid.
            if is_low_exposure and sentiment > 0.4:
                # 'score' is the Gemini/LLM prediction confidence
                confidence_score = fundamentals.get("score", 0)
                if confidence_score > 50:
                    final_action = "BUY"
                    conviction = 70  # Aggressive entry conviction
                    technical_signal = "LOW_EXPOSURE_PROACTIVE_ENTRY"

            # --- RSI OVERLAY (Oversold Aggression) ---
            if rsi <= 30 and sentiment > 0.4:
                final_action = "BUY"
                conviction = max(conviction, 75)
                technical_signal = "RSI_OVERSOLD_BUY"

        # 2. Strategic Exit Check (THE OVERRIDE)
        # If we already hold the stock, we check for Profit Target or Stop Loss FIRST.
        # This prevents the bot from "ignoring" a win just because the chart still looks good.
        if avg_price > 0:
            if self.should_exit(ticker, avg_price, current_price, sentiment):
                p_change = (current_price - avg_price) / avg_price
                final_action = "SELL"
                conviction = 100  # Exit is mandatory
                exit_type = (
                    "PROFIT_TARGET" if p_change >= 0.05 else "STOP_LOSS/SENTIMENT"
                )
                technical_signal = f"EXIT_{exit_type}"  # Update for the log line

            # RSI Overbought Exit
            elif rsi >= 80:
                final_action = "SELL"
                conviction = 100
                technical_signal = "RSI_OVERBOUGHT_EXIT"

        # 3. Fundamental Overlay (The Gatekeeper)
        # We now BLOCK buys if fundamentals are weak.
        if final_action == "BUY":
            f_score = fundamentals.get("f_score", 0)
            is_healthy = fundamentals.get("is_healthy", True)

            # HURDLE 1: Basic Profitability/Valuation
            if not is_healthy:
                final_action = "IDLE"
                conviction = 0
                technical_signal = "REJECT_UNHEALTHY"  # Update log

            # HURDLE 2: Deep Financial Health (F-Score)
            elif f_score < 5:
                # F-Score range is 0-9. < 5 implies mixed/poor signals.
                final_action = "IDLE"
                conviction = 0
                technical_signal = f"REJECT_WEAK_FSCORE_{f_score}"

            # BONUS: Boost for Elite Health
            elif f_score >= 7:
                conviction = min(100, conviction + 10)

        # 4. Conviction Enhancement via 'Lessons Learned'
        if lessons and "caution" in lessons.lower() and final_action == "BUY":
            conviction -= 10

        # 4. Final Sanity Check: Is Market Open?
        is_open = self.is_market_open()
        dry_run_prefix = ""
        if not is_open:
            dry_run_prefix = "[DRY-RUN] "
            # We keep the core action (BUY/SELL) so the bot logs the intent clearly.
            # main.py handles the actual execution avoidance via is_market_open().

        decision = {
            "ticker": ticker,
            "action": final_action,
            "conviction": conviction,
            "price": current_price,
            "timestamp": datetime.now().isoformat(),
            "meta": {
                "sentiment": sentiment,
                "technical": technical_signal,
                "rsi": rsi,
                "fundamentals_analyzed": fundamentals is not None,
                "is_open": is_open,
            },
        }

        # Log it using the correct signature: (ticker, action, reason, details)
        ai_score = fundamentals.get("score", 0)
        reason = f"{dry_run_prefix}Signal: {technical_signal} | Sent: {sentiment:.2f} | AI: {ai_score} | Conf: {conviction}"
        log_decision(ticker, final_action, reason, decision)

        return decision

    def calculate_position_size(
        self, ticker: str, cash_available: float, volatility: float = 0.02
    ) -> float:
        """
        Determines how much to buy using a pseudo-Kelly Criterion / Fixed Fractional.
        Returns the dollar amount to allocate.
        """
        # Risk no more than 2% of available cash on a single trade baseline
        # adjusted by volatility (lower vol -> higher size, but capped)
        allocation = Decimal(str(cash_available)) * self.risk_per_trade

        # Volatility Scaling (simplified)
        if volatility < 0.01:
            allocation *= Decimal("1.2")
        elif volatility > 0.03:
            allocation *= Decimal("0.8")

        return float(allocation)

    def should_exit(
        self, ticker: str, hold_price: float, current_price: float, sentiment: float
    ) -> bool:
        """
        Exit logic override: Exit if sentiment falls sharply even if BB says hold.
        """
        p_change = (current_price - hold_price) / hold_price

        # Exit if:
        # 1. 5% profit target hit
        if p_change >= 0.05:
            return True

        # 2. 2.5% stop loss hit
        if p_change <= -0.025:
            return True

        # 3. Negative Sentiment Shift (-0.4 or lower)
        if sentiment < -0.4:
            return True

        return False

    def check_conviction_swap(
        self,
        current_ticker: str,
        current_conf: int,
        potential_ticker: str,
        potential_conf: int,
        potential_fundamentals: Dict = None,
    ) -> bool:
        """
        Determines if we should SELL a current holding to BUY a much better opportunity.
        We swap only if:
        1. Potential confidence is significantly better (Hurdle Rate).
        2. Potential ticker is Fundamentally Strong (Gatekeeper).
        """
        # 1. Fundamental Gatekeeper
        if potential_fundamentals:
            # Must be "Deeply Healthy" to justify a forced swap
            if not potential_fundamentals.get("is_deep_healthy", False):
                return False

            # Optional: Enforce F-Score > 5 for swaps
            if potential_fundamentals.get("f_score", 0) < 5:
                return False

        # 2. Confidence Hurdle (Switching Cost buffer)
        # hurdle_rate might be 15-20% confidence difference
        if potential_conf > (current_conf + 15):
            return True

        return False
