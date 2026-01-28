# bot/main.py
import os
import asyncio
import httpx
from flask import Flask, jsonify
from telemetry import log_performance # ABSOLUTE IMPORT FIX

app = Flask(__name__)

@app.route("/")
def health_check():
    return "Aberfeldie Trading Node: Operational", 200

@app.route("/run-audit", methods=["POST"])
def run_audit():
    # 1. Context Fetching (Concurrent FX Poll)
    fx_rate = asyncio.run(get_fx_rate())
    
    # 2. Mock Portfolio Value (Placeholder for IBKR Actuator)
    current_equity_usd = 51250.0 
    
    # 3. Telemetry Execution
    metrics = log_performance(current_equity_usd, fx_rate)
    
    if metrics:
        return jsonify({"status": "success", "metrics": metrics}), 200
    else:
        return jsonify({"status": "error", "message": "Telemetry failure"}), 500

async def get_fx_rate():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("https://api.frankfurter.app/latest?from=USD&to=AUD")
            return r.json().get("rates", {}).get("AUD", 1.55)
        except:
            return 1.55 # Fallback

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

