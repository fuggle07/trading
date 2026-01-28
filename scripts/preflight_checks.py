import requests
import subprocess
import sys

# CONFIGURATION
NTFY_TOPIC = "aberfeldie_trading_alerts"
# Fetch your service URL automatically from terraform
try:
    SERVICE_URL = subprocess.check_output(
        ["terraform", "-chdir=/home/peterf/trading/terraform", "output", "-no-color", "-raw", "service_url"],
        text=True
    ).strip()
except:
    SERVICE_URL = "https://trading-audit-agent-848550797370.us-central1.run.app"

def run_preflight():
    print(f"Executing Pre-Flight check for: {SERVICE_URL}")
    
    try:
        # Generate a fresh identity token for the request
        token = subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{SERVICE_URL}/run-audit", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            equity = data.get('metrics', {}).get('paper_equity', 0)
            msg = f"✅ PRE-FLIGHT SUCCESS: Node is live. IBKR Equity: ${equity:.2f}"
            print(msg)
        else:
            send_alert(f"🚨 PRE-FLIGHT FAIL: Service returned {response.status_code}")
            
    except Exception as e:
        send_alert(f"💥 PRE-FLIGHT CRITICAL: Could not reach Node. Error: {str(e)[:100]}")

def send_alert(message):
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                  data=message.encode('utf-8'),
                  headers={"Priority": "high", "Tags": "warning,rotating_light"})

if __name__ == "__main__":
    run_preflight()

