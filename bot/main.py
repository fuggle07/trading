import asyncio
import os
import logging
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AberfeldieNode")

# --- AUTH GUARD ---
# Set this in your Secret Manager / Environment Variables
CRON_SECRET = os.getenv("INTERNAL_AUTH_TOKEN", "change-me")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "node": "Aberfeldie"}), 200

@app.route('/', methods=['POST', 'GET'])
def run_audit_wrapper():
    # Basic protection against "stupid" external triggers
    auth_token = request.headers.get("X-Internal-Token")
    if auth_token != CRON_SECRET:
        logger.warning({"event": "unauthorized_access", "ip": request.remote_addr})
        # For now, let's just log and continue, or return 403 to be strict
    
    try:
        # The Bridge: Runs your async code in a sync Flask route
        msg, code = asyncio.run(main_handler())
        return msg, code
    except Exception as e:
        logger.error({"event": "node_crash", "error": str(e)})
        return f"Node Error: {e}", 500

async def main_handler():
    # ... your existing logic (get_usd_aud_rate, etc.)
    # logger.info({"event": "audit_started"})
    return "Audit Complete", 200
