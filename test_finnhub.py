import os
import time
import finnhub
from google.cloud import secretmanager

# Fetch the REAL secret to test with
def get_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/utopian-calling-429014-r9/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

API_KEY = get_secret("FINNHUB_KEY")
print(f"🔑 Key loaded (len={len(API_KEY)})")

finnhub_client = finnhub.Client(api_key=API_KEY)
ticker = "NVDA"

# 1. Test Basic Quote
print(f"📡 Testing QUOTE for {ticker}...")
try:
    quote = finnhub_client.quote(ticker)
    print(f"✅ Quote Success: {quote}")
except Exception as e:
    print(f"❌ Quote FAILED: {e}")

# 2. Test Candles (Small Range)
end = int(time.time())
start = end - (5 * 24 * 60 * 60) # 5 days
print(f"📡 Testing CANDLES for {ticker} (Last 5 days, Daily)...")
try:
    res = finnhub_client.stock_candles(ticker, 'D', start, end)
    if res.get('s') == 'ok':
        print(f"✅ Candles Success! Got {len(res['c'])} candles.")
    else:
        print(f"⚠️  Candle Response 's': {res.get('s')} | Message: {res}")
except Exception as e:
    print(f"❌ Candles FAILED: {e}")
