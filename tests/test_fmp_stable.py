import subprocess
import requests

key = subprocess.run(["gcloud", "secrets", "versions", "access", "latest", "--secret=FMP_KEY"], capture_output=True, text=True).stdout.strip()
print("Key length:", len(key))

endpoints = [
    "profile?symbol=AAPL",
    "income-statement?symbol=AAPL",
    "balance-sheet-statement?symbol=AAPL",
    "cash-flow-statement?symbol=AAPL",
    "analyst-estimates?symbol=AAPL",
    "price-target-consensus?symbol=AAPL",
    "insider-trading/search?symbol=AAPL",
    "ratios-ttm?symbol=AAPL",
    "key-metrics-ttm?symbol=AAPL",
    "quote?symbol=AAPL"
]

for endpoint in endpoints:
    url = f"https://financialmodelingprep.com/stable/{endpoint}&apikey={key}"
    try:
        r = requests.get(url)
        print(f"{endpoint}: {r.status_code}")
        if r.status_code == 200:
            print(r.text[:100])
        else:
            print(r.text[:100])
    except Exception as e:
        print(f"Exception for {endpoint}: {e}")
