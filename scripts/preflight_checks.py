import requests
import subprocess
import os
from pathlib import Path

# CONFIGURATION
NTFY_TOPIC = "aberfeldie_trading_alerts_987"

SCRIPT_DIR = Path(__file__).resolve().parent
TF_DIR = SCRIPT_DIR.parent / "terraform"

def get_service_url():
    try:
        # Runs terraform output from the discovered directory
        return subprocess.check_output(
            ["terraform", f"-chdir={TF_DIR}", "output", "-no-color", "-raw", "service_url"],
            text=True
        ).strip()
    except Exception as e:
        print(f"Warning: Terraform lookup failed: {e}")
        # Fallback to your known service URL
        return "https://trading-audit-agent-848550797370.us-central1.run.app"

def run_preflight():
    url = get_service_url()
    print(f"Checking Aberfeldie Node at: {url}")
    
    try:
        # Get gcloud token
        token = subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(f"{url}/run-audit", headers=headers, timeout=30)
        
        if response.status_code == 200:
            equity = response.json().get('metrics', {}).get('paper_equity')
            requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                          data=f"✅ PRE-FLIGHT OK: Equity ${equity}".encode('utf-8'))
        else:
            raise Exception(f"Status {response.status_code}")
            
    except Exception as e:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", 
                      data=f"🚨 PRE-FLIGHT FAILED: {str(e)}".encode('utf-8'),
                      headers={"Priority": "high", "Tags": "warning"})

if __name__ == "__main__":
    run_preflight()

