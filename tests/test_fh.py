import os
import finnhub
from datetime import datetime, timedelta

def main():
    fh_key = os.environ.get("EXCHANGE_API_KEY") or os.environ.get("FINNHUB_KEY")
    if not fh_key:
        print("No fh key")
        return
    client = finnhub.Client(api_key=fh_key)
    end = int(datetime.now().timestamp())
    start = int((datetime.now() - timedelta(days=90)).timestamp())
    try:
        res = client.stock_candles('AAPL', 'D', start, end)
        print("Finnhub Response:", type(res), str(res)[:100] if res else None)
    except Exception as e:
        print("Finnhub Error:", e)

main()
