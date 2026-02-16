from decimal import Decimal
from typing import Optional, Dict

class SignalAgent:
    """
    The decision-making engine with built-in Volatility Filtering.
    """
    def __init__(self, risk_profile: float = 0.02, vol_threshold: float = 0.05):
        self.risk_per_trade = Decimal(str(risk_profile))
        # vol_threshold: 0.05 means if the bands are > 5% apart, we don't trade.
        self.vol_threshold = Decimal(str(vol_threshold))

    def evaluate_strategy(self, market_data: Dict) -> Optional[Dict]:
        """
        Evaluates signals only if the market volatility is within safe bounds.
        """
        # 1. Volatility Filter (The Gatekeeper)
        is_stable, vol_pct = self._check_volatility(market_data)
        if not is_stable:
            # We log this but return None to skip the trade
            print(f"Skipping trade: Volatility too high ({vol_pct:.2%})")
            return None

        # 2. Strategy Logic (SMA Crossover)
        price = Decimal(str(market_data['current_price']))
        sma_short = Decimal(str(market_data['sma_20']))
        sma_long = Decimal(str(market_data['sma_50']))

        if sma_short > sma_long:
            return {"action": "BUY", "price": price, "reason": "SMA_CROSSOVER_BULLISH"}
        elif sma_short < sma_long:
            return {"action": "SELL", "price": price, "reason": "SMA_CROSSOVER_BEARISH"}

        return None

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
