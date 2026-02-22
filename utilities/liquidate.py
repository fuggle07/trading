"""
Emergency Liquidation Utility
Usage: python3 utilities/liquidate.py
Description: Cancels all Alpaca orders, closes all positions, and resets the BigQuery ledger to $100k.
"""

#!/usr/bin/env python3
import sys
import os

# Ensure the project root is in the path so we can import 'bot'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import time
import requests
from google.cloud import bigquery

# Authentication & Configuration
ALPACA_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET")
BASE_URL = "https://paper-api.alpaca.markets"  # Hardcoded to paper for safety
HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}

PROJECT_ID = os.environ.get("PROJECT_ID")
INITIAL_EQUITY = 100000.0


def liquidate_alpaca():
    """Cancels all orders and closes all positions on Alpaca."""
    if not ALPACA_KEY or not ALPACA_SECRET:
        print("❌ ERROR: Alpaca keys missing. Cannot liquidate brokerage.")
        return False

    print("🛑 PANIC: Starting Alpaca Liquidation...")

    # 1. Cancel all open orders
    try:
        res = requests.delete(f"{BASE_URL}/v2/orders", headers=HEADERS)
        if res.status_code == 200:
            print("✅ All open orders cancelled.")
        else:
            print(f"⚠️ Order cancellation warning: {res.text}")
    except Exception as e:
        print(f"❌ Order cancellation failed: {e}")

    # 2. Close all positions
    try:
        res = requests.delete(f"{BASE_URL}/v2/positions", headers=HEADERS)
        if res.status_code == 207:
            print("✅ All positions closing...")
        elif res.status_code == 200:
            print("✅ No positions to close.")
        else:
            print(f"⚠️ Position liquidation warning: {res.text}")
    except Exception as e:
        print(f"❌ Position liquidation failed: {e}")

    return True


def reset_ledger():
    """Resets the BigQuery portfolio ledger to $100,000 USD."""
    if not PROJECT_ID:
        print("❌ ERROR: PROJECT_ID missing. Cannot reset ledger.")
        return False

    print(f"📊 Resetting BigQuery Ledger for project: {PROJECT_ID}...")
    client = bigquery.Client()
    table_ref = f"{PROJECT_ID}.trading_data.portfolio"

    try:
        # 1. Clear existing holdings
        client.query(f"TRUNCATE TABLE `{table_ref}`").result()

        # 2. Seed initial cash
        seed_query = f"""
        INSERT INTO `{table_ref}` (asset_name, holdings, cash_balance, avg_price, last_updated)
        VALUES ('USD', 0.0, {INITIAL_EQUITY}, 0.0, CURRENT_TIMESTAMP())
        """
        client.query(seed_query).result()
        print(f"✅ Ledger reset to ${INITIAL_EQUITY:,.2f} Cash.")
        return True
    except Exception as e:
        print(f"❌ Ledger reset failed: {e}")
        return False


if __name__ == "__main__":
    print("🚨🚨🚨 EMERGENCY LIQUIDATION TRIGGERED 🚨🚨🚨")
    success_alpaca = liquidate_alpaca()
    success_ledger = reset_ledger()

    if success_alpaca and success_ledger:
        print("\n✨ FINAL STATUS: System Flattened Successfully.")
    else:
        print("\n⚠️ FINAL STATUS: Partial Success. Check logs/brokerage manually.")
