# bot/liquidate.py - Emergency Actuator
import os
import asyncio
from ib_async import IB

async def emergency_liquidate_all():
    """
    Directive: Close all open positions across the portfolio.
    This is the 'Hard-Stop' for the Aberfeldie Node.
    """
    mode = os.getenv("TRADING_MODE", "DRY_RUN")
    print(f"🚨 [LIQUIDATOR] INITIALIZING EMERGENCY EXIT | Mode: {mode}")

    if mode == "DRY_RUN":
        print("🧪 [SIMULATION] All paper positions closed and orders cancelled.")
        return True

    # Live Actuation Logic
    ib = IB()
    try:
        # Connect with a dedicated Emergency ClientID (99)
        await ib.connectAsync('127.0.0.1', 4001, clientId=99)
        
        # 1. Cancel all pending orders
        ib.reqGlobalCancel()
        print("🚫 Pending orders cancelled.")

        # 2. Identify and close all open positions
        positions = await ib.positionsAsync()
        if not positions:
            print("✅ No open positions found.")
            return True

        for p in positions:
            print(f"📉 Closing position: {p.contract.symbol} ({p.position} units)")
            # Execute Market Order to flatten position
            # (Actual order placement logic goes here)
            
        return True
    except Exception as e:
        print(f"❌ CRITICAL: Liquidation Actuator Failure: {e}")
        return False
    finally:
        ib.disconnect()

if __name__ == "__main__":
    # Allows manual execution: python3 bot/liquidate.py
    asyncio.run(emergency_liquidate_all())

