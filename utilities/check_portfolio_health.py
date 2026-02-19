"""
Portfolio Fundamental Health Audit
Usage: python3 utilities/check_portfolio_health.py
Description: Audits the fundamental health (Quality Score, F-Score) of all held positions in BigQuery.
"""
#!/usr/bin/env python3
import asyncio
import os
import sys

# Ensure the project root is in the path so we can import 'bot'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import bigquery
from bot.fundamental_agent import FundamentalAgent

PROJECT_ID = os.getenv("PROJECT_ID", "utopian-calling-429014-r9")

async def audit_portfolio():
    print(f"🔍 Auditing Portfolio Fundamentals for {PROJECT_ID}...")
    
    # 1. Get Holdings
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT asset_name as ticker, holdings, avg_price 
        FROM `{PROJECT_ID}.trading_data.portfolio`
        WHERE holdings > 0
    """
    rows = client.query(query).result()
    holdings = [row.ticker for row in rows]
    
    if not holdings:
        print("✅ Portfolio is empty. Nothing to check.")
        return

    print(f"📊 Analyzing {len(holdings)} positions: {holdings}")
    
    # 2. Analyze
    agent = FundamentalAgent()
    
    results = []
    print(f"{'TICKER':<10} | {'HEALTHY':<8} | {'F-SCORE':<8} | {'REASON'}")
    print("-" * 60)
    
    for ticker in holdings:
        is_deep, reason, f_score = await agent.evaluate_deep_health(ticker)
        
        status = "✅ PASS" if (is_deep and f_score >= 5) else "❌ FAIL"
        if f_score < 5: status = "❌ WEAK"
        if not is_deep: status = "❌ BAD"
        
        print(f"{ticker:<10} | {status:<8} | {f_score:<8} | {reason}")
        results.append((ticker, status, f_score, reason))
        
    print("-" * 60)
    
    # Warning Summary
    failures = [r for r in results if "FAIL" in r[1] or "WEAK" in r[1] or "BAD" in r[1]]
    if failures:
        print(f"\n⚠️  Found {len(failures)} stocks that fail the new hurdles:")
        for f in failures:
            print(f"- {f[0]}: {f[3]} (F-Score: {f[2]})")
    else:
        print("\n🎉 All stocks pass the fundamental checks!")

if __name__ == "__main__":
    asyncio.run(audit_portfolio())
