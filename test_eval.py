import os
from decimal import Decimal


class MockSignalAgent:
    def __init__(self):
        self.vol_threshold = Decimal("0.05")

    def evaluate_bands(self, current_price, upper, lower, is_low_exposure=False):
        price = Decimal(str(current_price))
        up = Decimal(str(upper))
        lo = Decimal(str(lower))
        if price <= 0:
            return "HOLD"
        band_width = (up - lo) / price
        effective_vol_threshold = self.vol_threshold
        if is_low_exposure:
            effective_vol_threshold *= Decimal("1.5")
        if band_width > effective_vol_threshold:
            return "VOLATILE_IGNORE"
        if price >= up:
            return "SELL"
        elif price <= lo:
            return "BUY"
        # wait! What if price > lo and price < up? It returns "HOLD"
        return "HOLD"


agent = MockSignalAgent()
print(agent.evaluate_bands(1009.52, 1050, 950, True))
