import requests
import json
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# We can query gcloud directly if the python package is unhappy
result = subprocess.run(
    ["gcloud", "secrets", "versions", "access", "latest", "--secret=FMP_KEY"], 
    capture_output=True, text=True
)
key = result.stdout.strip()

if not key:
    print("NO KEY")
    exit(1)

urls_to_test = [
    f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/v3/profile/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/v3/quote/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/api/v3/income-statement/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/v3/income-statement/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/api/v3/cash-flow-statement/AAPL?apikey={key}",
    f"https://financialmodelingprep.com/v3/cash-flow-statement/AAPL?apikey={key}"
]

for url in urls_to_test:
    print(f"Testing: {url.replace(key, 'XXX')}")
    try:
        r = requests.get(url)
        print(f"Status: {r.status_code}")
        if r.status_code != 200:
            print(f"Error text: {r.text[:100]}")
        else:
            print(f"Success! Snippet length: {len(r.text)}")
    except Exception as e:
        print(f"Exception: {e}")
    print("-" * 40)
