import asyncio
import os
import sys

# Add project root and bot directory to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'bot'))

from bot.main import run_audit, check_api_key

# Ensure API key is present
if not check_api_key():
    print("❌ EXCHANGE_API_KEY is missing")
    sys.exit(1)

async def main():
    print("🚀 Starting reproduction script...")
    results = await run_audit()
    print("✅ Audit complete.")
    print(f"Results: {results}")

if __name__ == "__main__":
    asyncio.run(main())
