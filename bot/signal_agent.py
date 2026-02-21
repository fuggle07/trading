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

    def evaluate_bands(self, current_price: float, upper: float, lower: float, is_low_exposure: bool = False) -> str:
        """
        Calculates signal based on Bollinger Bands.
        Includes a Volatility Filter (vol_threshold).
        """
        price = Decimal(str(current_price))
        up = Decimal(str(upper))
        lo = Decimal(str(lower))

        # Calculate Band Width % (Volatility Filter)
        band_width = (up - lo) / price
        
        effective_vol_threshold = self.vol_threshold
        if is_low_exposure:
            # Relax volatility filter by 50% when exposure is low to force activity
            effective_vol_threshold *= Decimal("1.5")

        if band_width > effective_vol_threshold:
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
        log_results: bool = True,
    ) -> Dict:
        """
        Orchestrates Signal Selection by combining technicals, sentiment, and fundamental conviction.
        """
        ticker = market_data.get("ticker", "Unknown")
        current_price = float(market_data.get("current_price") if market_data.get("current_price") is not None else 0.0)
        indicators = {
            "upper": float(market_data.get("bb_upper") if market_data.get("bb_upper") is not None else 0.0),
            "lower": float(market_data.get("bb_lower") if market_data.get("bb_lower") is not None else 0.0),
            "sma_20": float(market_data.get("sma_20") if market_data.get("sma_20") is not None else 0.0),
            "sma_50": float(market_data.get("sma_50") if market_data.get("sma_50") is not None else 0.0),
        }
        sentiment = float(market_data.get("sentiment_score") if market_data.get("sentiment_score") is not None else 0.0)
        volume = float(market_data.get("volume") if market_data.get("volume") is not None else 0.0)
        avg_volume = float(market_data.get("avg_volume") if market_data.get("avg_volume") is not None else 1.0)
        days_to_earnings = market_data.get("days_to_earnings") # None if unknown

        fundamentals = {
            "is_healthy": market_data.get("is_healthy", True),
            "health_reason": market_data.get("health_reason", ""),
            "is_deep_healthy": market_data.get("is_deep_healthy", True),
            "deep_health_reason": market_data.get("deep_health_reason", ""),
            "f_score": market_data.get("f_score", 0),  # Piotroski F-Score
            "score": market_data.get("prediction_confidence", 0),
        }
        avg_price = float(market_data.get("avg_price") if market_data.get("avg_price") is not None else 0.0)
        is_low_exposure = market_data.get("is_low_exposure", False)
        rsi = float(market_data.get("rsi") if market_data.get("rsi") is not None else 50.0)
        lessons = ""  # Placeholder for now

        technical_signal = self.evaluate_bands(
            current_price, indicators.get("upper", 0), indicators.get("lower", 0), is_low_exposure
        )

        # --- MOMENTUM BREAKOUT OVERLAY ---
        # If breaking ABOVE upper band on 1.5x volume, this is a MOMENTUM BUY, not a SELL.
        # This overrides the default mean-reversion SELL signal.
        if current_price >= indicators.get("upper", 0) and volume > (1.5 * avg_volume):
            technical_signal = "MOMENTUM_BREAKOUT"

        # Logic for Final Decision
        final_action = "IDLE"
        conviction = 0
        sentiment_gate = 0.4  # Slightly biased towards caution

        # 1. Technical Baseline
        if technical_signal == "BUY" and sentiment >= sentiment_gate:
            final_action = "BUY"
            conviction = 60 + int(sentiment * 40)  # [60 - 100]
        elif technical_signal == "MOMENTUM_BREAKOUT" and sentiment >= 0.5:
            # Momentum requires even stronger sentiment confirmation
            final_action = "BUY"
            conviction = 80 + int(sentiment * 20)
        elif technical_signal == "SELL":
            final_action = "SELL"
            conviction = 80
        elif technical_signal == "VOLATILE_IGNORE":
            final_action = "IDLE"
            conviction = 0
        else:
            final_action = "IDLE"
            # ENHANCEMENT: Low Exposure Aggression
            if is_low_exposure:
                if sentiment >= 0.2 and fundamentals.get("score", 0) >= 70:
                    final_action = "BUY"
                    conviction = 70
                    technical_signal = "PROACTIVE_WARRANTED_ENTRY"
            
            # --- RSI OVERLAY (Oversold Aggression) ---
            if rsi <= 30 and sentiment > 0.4:
                final_action = "BUY"
                conviction = max(conviction, 75)
                technical_signal = "RSI_OVERSOLD_BUY"

        # --- EARNINGS CALENDAR AVOIDANCE ---
        # Skip BUY signals if earnings are within 3 days (binary event risk)
        if final_action == "BUY" and days_to_earnings is not None and days_to_earnings <= 3:
            final_action = "IDLE"
            conviction = 0
            technical_signal = f"SKIP_EARNINGS_AVOIDANCE_{days_to_earnings}D"

        # 2. Strategic Exit Check (THE OVERRIDE)
        # If we already hold the stock, we check for Profit Target or Stop Loss FIRST.
        if avg_price > 0:
            hwm = market_data.get("hwm", 0.0)
            vix = market_data.get("vix", 0.0)
            band_width = market_data.get("band_width", 0.0)
            has_scaled_out = market_data.get("has_scaled_out", False)

            exit_signal = self.should_exit(
                ticker, 
                avg_price, 
                current_price, 
                sentiment, 
                band_width, 
                vix, 
                hwm, 
                has_scaled_out
            )

            if exit_signal != "HOLD":
                final_action = exit_signal # "SELL_ALL" or "SELL_PARTIAL_50"
                conviction = 100
                technical_signal = f"EXIT_{exit_signal}"

                # Double check for RSI overbought even if should_exit said HOLD
                if rsi >= 85:
                    final_action = "SELL_ALL"
                    technical_signal = "RSI_EXTREME_OVERBOUGHT"

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
            # F-Score is 0-9. None = Data Missing.
            f_score = fundamentals.get("f_score")
            ai_confidence = fundamentals.get("score", 0)


            if f_score is None:
                # CASE A: Missing Data -> Require reasonable AI Confidence to proceed blindly
                if ai_confidence < 70:
                    final_action = "IDLE"
                    conviction = 0
                    technical_signal = "REJECT_INSUFFICIENT_DATA"
                else:
                    # Proceed with "PROACTIVE" but with lower conviction since data is missing
                    # If sentiment is good, allow it. Standardizing on 0.2 hurdle
                    if sentiment >= 0.2:
                        final_action = "BUY"
                        conviction = 70
                        technical_signal = "PROACTIVE_WARRANTED_DATA_MISSING_BYPASS"
                    else:
                        final_action = "IDLE"
                        conviction = 0
                        technical_signal = "REJECT_LOW_SENTIMENT_DATA_MISSING"

            elif f_score <= 1:
                # CASE B: Confirmed Bad Fundamentals -> Turnaround Play requirements
                # Relaxed from 80/0.6 to 70/0.4 to enable NVDA/MU while debugging F-Score
                if ai_confidence >= 70 and sentiment >= 0.4:
                    final_action = "BUY"
                    conviction = 75
                    technical_signal = f"TURNAROUND_WARRANTED_FSCORE_{f_score}"
                else:
                    final_action = "IDLE"
                    conviction = 0
                    technical_signal = f"REJECT_CONFIRMED_BAD_FSCORE_{f_score}"

            else:
                # CASE C: Normal/Good Fundamentals -> Use dynamic threshold
                f_score_threshold = 2 if is_low_exposure else 5
                
                if f_score < f_score_threshold:
                    # Check for bypass if low-ish score but high AI confidence
                    bypass_threshold = 65 if is_low_exposure else 80
                    if ai_confidence >= bypass_threshold:
                        technical_signal = f"BUY_FSCORE_{f_score}_BYPASS"
                        conviction = max(conviction, 80)
                    else:
                        final_action = "IDLE"
                        conviction = 0
                        technical_signal = f"REJECT_LOW_FSCORE_{f_score}"

            # BONUS: Boost for Elite Health
            if f_score is not None and f_score >= 7:
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

        # 5. Star Rating Classification
        # Star = High AI Conviction (90+) + Elite Fundamentals (F-Score 7+) + Deeply Healthy
        is_star = False
        ai_score = fundamentals.get("score", 0)
        
        if (
            ai_score >= 90
            and fundamentals.get("f_score") is not None
            and fundamentals.get("f_score", 0) >= 7
            and fundamentals.get("is_deep_healthy", True)
        ):
            is_star = True
            technical_signal = f"STAR_{technical_signal}"

        decision = {
            "ticker": ticker,
            "action": final_action,
            "conviction": conviction,
            "price": current_price,
            "timestamp": datetime.now().isoformat(),
            "meta": {
                "sentiment": sentiment,
                "ai_score": ai_score,
                "technical": technical_signal,
                "rsi": rsi,
                "fundamentals_analyzed": fundamentals is not None,
                "is_open": is_open,
                "is_star": is_star,
            },
        }

        # Reorder: Signal column at the end for readability
        reason = f"{dry_run_prefix}Sent: {sentiment:.2f} | AI: {ai_score} | Conf: {conviction} | Signal: {technical_signal}"
        decision["reason"] = reason

        # Log it using the correct signature: (ticker, action, reason, details)
        if log_results:
            log_decision(ticker, final_action, reason, decision)

        return decision

    def calculate_position_size(
        self, 
        total_equity: float, 
        conviction: int, 
        vix: float = 20.0, 
        band_width: float = 0.02,
        is_star: bool = False
    ) -> float:
        """
        Dynamic Position Sizing.
        Determines allocation such that the risk taken scales with conviction:
        - Baseline: 60 Conviction -> Risk 0.5% of equity if stopped at 2.5%.
        - Elite: 100 Conviction -> Risk 1.0% of equity (max 40% position).
        - VIX Damper: Reduces risk budget by 20% for every 10 points above VIX 20.
        """
        equity = Decimal(str(total_equity))
        
        # 1. Determine Risk Budget (% of equity to lose if stopped at 2.5%)
        # Scale risk linearly from 0.4% (at 50 conf) to 1.0% (at 100 conf)
        risk_pct = Decimal(str(max(0.004, min(0.01, (conviction / 100.0) * 0.01))))
        
        # 2. VIX Damper (Fear Adjustment)
        # If VIX > 20, reduce risk budget. E.g., VIX 40 reduces risk by 40%.
        if vix > 20:
            fear_factor = Decimal(str(max(0.5, 1.0 - ((vix - 20) / 100.0))))
            risk_pct *= fear_factor

        # 3. Ticker Volatility Damper
        # If Band Width > 5%, reduce risk budget (less certainty in wide bands)
        if band_width > 0.05:
            vol_damper = Decimal(str(max(0.6, 1.0 - (band_width - 0.05))))
            risk_pct *= vol_damper

        # 4. Derive Position Size from Risk Budget
        # Since our stop is ~2.5% (dynamic), we solve: Size * 0.025 = Equity * risk_pct
        # Size = (Equity * risk_pct) / 0.025
        # We use 0.025 as the standard stop-loss distance for sizing math.
        allocation = (equity * risk_pct) / Decimal("0.025")

        # 5. Elite/Star Minimums
        if is_star and allocation < (equity * Decimal("0.20")):
            allocation = equity * Decimal("0.20")

        # 6. Hard Caps (Max 40% per stock)
        max_cap = equity * Decimal("0.40")
        return float(min(allocation, max_cap))

    def should_exit(
        self,
        ticker: str,
        hold_price: float,
        current_price: float,
        sentiment: float,
        band_width: float = 0.0,
        vix: float = 0.0,
        hwm: float = 0.0,
        has_scaled_out: bool = False,
    ) -> str:
        """
        Exit logic with Trailing Stop and partial profit-taking (Scale Out).
        Returns: "HOLD", "SELL_ALL", or "SELL_PARTIAL_50"
        """
        p_change = (current_price - hold_price) / hold_price

        # 1. Partial Profit Taking (Scale Out): Sell 50% at +5% profit
        #    Only if we haven't already scaled out.
        if p_change >= 0.05 and not has_scaled_out:
            return "SELL_PARTIAL_50"

        # 2. Trailing Stop: Activates after +3% gain. 
        #    Sell remaining if pulls back 2% from peak (HWM).
        if p_change >= 0.03 or hwm >= hold_price * 1.03:
            if hwm > 0 and current_price <= hwm * 0.98:
                return "SELL_ALL"

        # 3. Dynamic stop loss: scale with volatility so we don't whipsaw on volatile stocks.
        #    Base = 2.5%. Volatile stocks get a wider stop, capped at 6%.
        if band_width > 0:
            dynamic_stop = max(0.025, min(0.06, band_width * 0.50))
        else:
            dynamic_stop = 0.025
        
        if p_change <= -dynamic_stop:
            return "SELL_ALL"

        # 4. Negative Sentiment Shift — tighten exit threshold if VIX is elevated
        sentiment_exit_threshold = -0.3 if vix > 25 else -0.4
        if sentiment < sentiment_exit_threshold:
            return "SELL_ALL"

        return "HOLD"

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
        # Increased to 25% for 65/35 strategy to minimize churn
        if potential_conf > (current_conf + 25):
            return True

        return False

    def evaluate_macro_hedge(self, macro_data: Dict) -> tuple[str, float]:
        """
        Determines the portfolio hedge status and target percentage based on market risk.
        Returns: (status, target_percentage)
        
        Tiers:
        - Panic (10%): VIX > 45
        - Fear (5%):  QQQ < SMA-50 AND VIX > 35
        - Caution (2%): QQQ < SMA-50 OR VIX > 30
        - Minimal: Market is healthy
        """
        indices = macro_data.get("indices", {})
        vix = float(macro_data.get("vix", 0.0))

        # 1. Nasdaq Trend Check
        qqq_price = indices.get("qqq_price", 0.0)
        qqq_sma50 = indices.get("qqq_sma50", 0.0)
        is_bearish_trend = qqq_price > 0 and qqq_sma50 > 0 and qqq_price < qqq_sma50

        # --- DYNAMIC SCALING TIERS ---
        if vix > 45.0:
            return "BUY_HEDGE", 0.10  # Panic level
        
        if is_bearish_trend and vix > 35.0:
            return "BUY_HEDGE", 0.05  # High Fear
            
        if is_bearish_trend or vix > 30.0:
            return "BUY_HEDGE", 0.02  # Caution
        
        return "CLEAR_HEDGE", 0.0
