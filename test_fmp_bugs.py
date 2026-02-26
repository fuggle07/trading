import requests
import subprocess
import json

key = subprocess.run(["gcloud", "secrets", "versions", "access", "latest", "--secret=FMP_KEY"], capture_output=True, text=True).stdout.strip()
finnhub_key = subprocess.run(["gcloud", "secrets", "versions", "access", "latest", "--secret=FINNHUB_KEY"], capture_output=True, text=True).stdout.strip()

print("Testing FMP Earning Calendar and Quotes")
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")

urls = [
    f"https://financialmodelingprep.com/stable/earning-calendar?from={today}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/stable/earning_calendar?from={today}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/api/v3/earning_calendar?from={today}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/api/v3/earning_calendar?apikey={key}",
    f"https://financialmodelingprep.com/stable/economic-calendar?from={today}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/api/v3/economic_calendar?from={today}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/stable/quote?symbol=AAPL,MSFT&apikey={key}",
    f"https://financialmodelingprep.com/api/v3/quote/AAPL,MSFT?apikey={key}"
]

for url in urls:
    print(f"URL: {url.replace(key, 'XXX')}")
    r = requests.get(url)
    print(f"Status: {r.status_code}")
    print(f"Snippet: {r.text[:100]}")
    print("-")

print("Testing Finnhub Economic Calendar")
try:
    import finnhub
    fh_client = finnhub.Client(api_key=finnhub_key)
    res = fh_client.calendar_economic()
    print("Finnhub Economic Calendar SUCCESS", str(res)[:100])
except Exception as e:
    print("Finnhub Error:", e)
