import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("FMP_KEY")
if not key:
    print("NO KEY")
    exit(1)

endpoints = [
  f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={key}",
  f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={key}",
  f"https://financialmodelingprep.com/api/v3/technical_indicator/1day/AAPL?type=sma&period=20&apikey={key}"
]

for url in endpoints:
    try:
        r = requests.get(url)
        print(url.replace(key, "XXX")[:70], r.status_code)
        try:
            data = r.json()
            print(str(data)[:100])
        except:
            print(r.text[:100])
    except Exception as e:
        print("ERROR:", e)
