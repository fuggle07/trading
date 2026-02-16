from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime
import pytz


class SignalAgent:
    """
    The decision-making engine with built-in Volatility Filtering and Holiday Awareness.
    """
    def __init__(self, risk_profile: float = 0.02, vol_threshold: float = 0.05):
        self.risk_per_trade = Decimal(str(risk_profile))
        # vol_threshold: 0.05 means if the bands are > 5% apart, we don't trade.
        self.vol_threshold = Decimal(str(vol_threshold))

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

    def _is_market_holiday(self):
        """Checks if today is a scheduled market holiday in New York time."""
        ny_tz = pytz.timezone('America/New_York')
        today_str = datetime.now(ny_tz).strftime('%Y-%m-%d')
        return today_str in self.market_holidays

    def evaluate_strategy(self, market_data: Dict) -> Optional[Dict]:
        """
        Evaluates signals only if the market is open and volatility is within safe bounds.
        """
        # 1. Holiday Filter
        if self._is_market_holiday():
            print(f"Skipping: Market is closed for holiday today.")
            return None

        # 2. Volatility Filter (The Gatekeeper)
        is_stable, vol_pct = self._check_volatility(market_data)
        if not is_stable:
            # We log this but return None to skip the trade
            print(f"Skipping trade: Volatility too high ({vol_pct:.2%})")
            return None

        # 3. Strategy Logic (SMA Crossover)
        price = Decimal(str(market_data['current_price']))
        sma_short = Decimal(str(market_data['sma_20']))
        sma_long = Decimal(str(market_data['sma_50']))
        
        signal = None
        if sma_short > sma_long:
            signal = {"action": "BUY", "price": price, "reason": "SMA_CROSSOVER_BULLISH"}
        elif sma_short < sma_long:
            signal = {"action": "SELL", "price": price, "reason": "SMA_CROSSOVER_BEARISH"}

        # 3b. Stop Loss Override (Safety Net)
        # If we own it (implied by having an avg_price > 0) and price is down 10%
        avg_price = Decimal(str(market_data.get('avg_price', 0.0)))
        if avg_price > 0:
            stop_price = avg_price * Decimal("0.90")
            if price < stop_price:
                 print(f"🚨 STOP LOSS TRIGGERED: Price {price} < {stop_price} (Avg: {avg_price})")
                 signal = {"action": "SELL", "price": price, "reason": "STOP_LOSS_HIT"}

        # 4. Sentiment Filter (The Vibe Check) - Apply ONLY to BUYs
        # We want to be able to SELL even if sentiment is terrible (especially then!)
        if signal and signal['action'] == 'BUY':
            sentiment = market_data.get('sentiment_score')
            if sentiment is not None and sentiment < -0.5:
                 print(f"Skipping BUY: Market sentiment is negative ({sentiment:.2f})")
                 return None

        return signal

    def _check_volatility(self, market_data: Dict) -> tuple[bool, Decimal]:
        """
        Calculates the width of Bollinger Bands relative to the price.
        Returns (is_stable, current_volatility_percentage).
        """
        upper_band = Decimal(str(market_data['bb_upper']))
        lower_band = Decimal(str(market_data['bb_lower']))
        current_price = Decimal(str(market_data['current_price']))

        # Calculate band width as a percentage of price
        vol_pct = (upper_band - lower_band) / current_price

        # If the gap is too wide, the 'edge' is lost in the noise
        return (vol_pct <= self.vol_threshold, vol_pct)
