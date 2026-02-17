
import os
import logging
from alpha_vantage.fundamentaldata import FundamentalData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestAV")

def test_av():
    key = os.getenv("ALPHA_VANTAGE_KEY")
    if not key:
        print("❌ No ALPHA_VANTAGE_KEY found")
        return

    fd = FundamentalData(key=key, output_format="json")
    ticker = "AAPL"
    
    print(f"📡 Testing Statement Endpoints for {ticker}...")
    try:
        # 1. Income
        income, _ = fd.get_income_statement_quarterly(symbol=ticker)
        print(f"✅ Income Statement fetched. Keys: {income.keys() if isinstance(income, dict) else 'Not a dict'}")
        
        # 2. Balance Sheet
        balance, _ = fd.get_balance_sheet_annual(symbol=ticker)
        print(f"✅ Balance Sheet fetched. Keys: {balance.keys() if isinstance(balance, dict) else 'Not a dict'}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_av()
