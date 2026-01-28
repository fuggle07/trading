import requests
import subprocess
from pathlib import Path

# Use the same unique topic you set in your phone app
NTFY_TOPIC = "aberfeldie_trading_alerts_987" 

def send_heartbeat():
    try:
        # Get Service URL
        script_dir = Path(__file__).resolve().parent
        tf_dir = script_dir.parent / "terraform"
        url = subprocess.check_output(
            ["terraform", f"-chdir={tf_dir}", "output", "-no-color", "-raw", "service_url"],
            text=True
        ).strip()

        # Get Token & Run Audit
        token = subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()
        response = requests.post(f"{url}/run-audit", headers={"Authorization": f"Bearer {token}"}, timeout=20)
        
        if response.status_code == 200:
            data = response.json().get('metrics', {})
            msg = f"🌙 Nightly Heartbeat: System OK.\nEquity: ${data.get('paper_equity')}\nAUD/USD: {data.get('fx_rate_aud')}"
            requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode('utf-8'))
        else:
            requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data="⚠️ Heartbeat Warning: Audit endpoint returned error.".encode('utf-8'))
            
    except Exception as e:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=f"❌ Heartbeat Failed: {str(e)[:50]}".encode('utf-8'))

if __name__ == "__main__":
    send_heartbeat()

