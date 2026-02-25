import requests
import json
import os

key = os.getenv("FMP_KEY", "b390cd9fca4dbbc1b2dd7ea349dbfe91") # Try to use the env var, fallback to a dummy or ask user
# Actually FMP_KEY is probably in the env. Let's source it.
