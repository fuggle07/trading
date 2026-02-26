import requests
import subprocess
import json

key = subprocess.run(["gcloud", "secrets", "versions", "access", "latest", "--secret=FMP_KEY"], capture_output=True, text=True).stdout.strip()
finnhub_key = subprocess.run(["gcloud", "secrets", "versions", "access", "latest", "--secret=FINNHUB_KEY"], capture_output=True, text=True).stdout.strip()

print("Testing FMP Earning Calendar and Quotes")
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")

urls = [
    f"https://financialmodelingprep.com/stable/earning-calendar?symbol=AAPL&apikey={key}",
    f"https://financialmodelingprep.com/stable/earning-calendar?symbol=AAPL&from={today}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/stable/earning_calendar?symbol=AAPL&apikey={key}",
    f"https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey={key}",
    f"https://financialmodelingprep.com/stable/quote?symbols=AAPL,MSFT&apikey={key}",
    f"https://financialmodelingprep.com/stable/quote-short?symbol=AAPL,MSFT&apikey={key}"
]

for url in urls:
    print(f"URL: {url.replace(key, 'XXX')}")
    r = requests.get(url)
    print(f"Status: {r.status_code}")
    print(f"Snippet: {r.text[:100]}")
    print("-")
