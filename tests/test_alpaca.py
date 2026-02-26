import os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
import datetime

def main():
    k = os.getenv("ALPACA_API_KEY")
    s = os.getenv("ALPACA_API_SECRET")
    print(bool(k), bool(s))
    c = StockHistoricalDataClient(k, s)
    req = StockBarsRequest(
        symbol_or_symbols="LMT",
        timeframe=TimeFrame.Day,
        start=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90),
        feed="iex"
    )
    b = c.get_stock_bars(req)
    print(b)
main()
