import os
import requests

KEY = os.getenv("FMP_KEY")
if not KEY:
    print("No FMP_KEY found.")
    exit(1)

endpoints = [
    f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={KEY}",
    f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={KEY}",
    f"https://financialmodelingprep.com/api/v3/income-statement/AAPL?limit=1&apikey={KEY}",
    f"https://financialmodelingprep.com/api/v3/search?query=AAPL&limit=1&apikey={KEY}",
    f"https://financialmodelingprep.com/api/v3/stock/list?limit=1&apikey={KEY}",
    f"https://financialmodelingprep.com/api/v3/market-hours?apikey={KEY}",
    f"https://financialmodelingprep.com/api/v4/price/AAPL?apikey={KEY}",
    f"https://financialmodelingprep.com/api/v3/quote-short/AAPL?apikey={KEY}",
]

print(f"Testing {len(endpoints)} endpoints with key length {len(KEY)}...")

for url in endpoints:
    try:
        r = requests.get(url, timeout=5)
        clean_url = url.split("?")[0]
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "Error Message" in data:
                print(f"❌ {clean_url}: 200 OK but API Error: {data['Error Message'][:50]}...")
            else:
                print(f"✅ {clean_url}: SUCCESS")
        else:
            print(f"❌ {clean_url}: {r.status_code}")
    except Exception as e:
        print(f"❌ {clean_url}: Exception {e}")
