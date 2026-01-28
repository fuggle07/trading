import os
import requests
import pytz
from datetime import datetime
from google.cloud import bigquery

# CONFIGURATION
PROJECT_ID = "utopian-calling-429014-r9"
ALPHA_THRESHOLD = -5.00
NTFY_TOPIC = "aberfeldie_trading_alerts"

def is_market_open():
    """Checks if the Nasdaq is currently in regular trading hours."""
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.now(ny_tz)
    
    # Nasdaq Regular Hours: 9:30 AM - 4:00 PM ET, Monday-Friday
    is_weekday = ny_now.weekday() < 5
    is_trading_hours = (ny_now.hour == 9 and ny_now.minute >= 30) or (10 <= ny_now.hour < 16)
    
    return is_weekday and is_trading_hours

def check_alpha():
    if not is_market_open():
        print("Nasdaq is closed. Skipping alert check to avoid noise.")
        return

    client = bigquery.Client(project=PROJECT_ID)
    query = f"SELECT net_alpha_usd, recommendation FROM `{PROJECT_ID}.trading_data.performance_logs` ORDER BY timestamp DESC LIMIT 1"
    
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        if results:
            latest_alpha = results[0].net_alpha_usd
            if latest_alpha < ALPHA_THRESHOLD:
                msg = f"📉 ALPHA ALERT: ${latest_alpha:.2f} USD. Market is LIVE."
                requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode('utf-8'))
    except Exception as e:
        print(f"Error checking alpha: {e}")

if __name__ == "__main__":
    check_alpha()

