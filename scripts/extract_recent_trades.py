#!/usr/bin/env python3
import os
import csv
import argparse
from google.cloud import bigquery
from datetime import datetime
import pytz

def extract_trades(hours=24, output_file=None):
    project_id = os.getenv("PROJECT_ID")
    if not project_id:
        print("Error: PROJECT_ID environment variable is not set. Are you running this via 'source .env'?")
        return

    client = bigquery.Client(project=project_id)
    
    if not output_file:
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"recent_trades_{hours}h_{timestamp_str}.csv"
        
    print(f"Extracting trades from the last {hours} hours...")
    
    # We query the executions table, and join it with the most recent watchlist_logs 
    # record for the same ticker that occurred BEFORE the execution.
    # This gives us the snapshot of AI reasoning, sentiment, volatility (band width), etc.
    query = f"""
    WITH RecentTrades AS (
        SELECT 
            e.timestamp,
            e.execution_id,
            e.ticker,
            e.action AS BUY_SELL,
            e.reason AS reason_signal,
            e.price,
            e.status
        FROM `{project_id}.trading_data.executions` e
        WHERE e.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
    ),
    ClosestWatchlist AS (
        SELECT 
            w.ticker,
            w.timestamp AS w_timestamp,
            w.gemini_reasoning AS AI,
            w.sentiment_score AS Sent,
            w.rsi AS RSI,
            SAFE_DIVIDE((w.bb_upper - w.bb_lower), w.price) AS Vlty,
            w.f_score AS F_Score,
            w.conviction AS Conf
        FROM `{project_id}.trading_data.watchlist_logs` w
        WHERE w.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours + 48} HOUR)
    ),
    ClosestFundamental AS (
        SELECT 
            f.ticker,
            f.timestamp AS f_timestamp,
            f.is_healthy
        FROM `{project_id}.trading_data.fundamental_cache` f
        WHERE f.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours + 48} HOUR)
    ),
    Matched AS (
        SELECT 
            t.timestamp,
            t.ticker,
            t.BUY_SELL,
            COALESCE(TRIM(REGEXP_EXTRACT(t.reason_signal, r'(Signal:\\s*[^|]+)')), t.reason_signal) AS extracted_signal,
            COALESCE(TRIM(REGEXP_EXTRACT(t.reason_signal, r'(AI:\\s*\\d+)')), '') AS extracted_ai_score,
            c.AI AS gemini_ai,
            c.Sent,
            c.RSI,
            c.Vlty,
            c.F_Score,
            c.Conf,
            t.price,
            t.status
        FROM RecentTrades t
        LEFT JOIN ClosestWatchlist c 
          ON t.ticker = c.ticker 
          AND c.w_timestamp <= t.timestamp
        -- Get the closest prior matching watchlist entry for this exact execution
        QUALIFY ROW_NUMBER() OVER(PARTITION BY t.execution_id ORDER BY c.w_timestamp DESC) = 1
    ),
    MatchedWithHealth AS (
        SELECT 
            m.*,
            cf.is_healthy
        FROM Matched m
        LEFT JOIN ClosestFundamental cf 
          ON m.ticker = cf.ticker 
          AND cf.f_timestamp <= m.timestamp
        QUALIFY ROW_NUMBER() OVER(PARTITION BY m.ticker, m.timestamp ORDER BY cf.f_timestamp DESC) = 1
    )
    SELECT * FROM MatchedWithHealth
    ORDER BY timestamp DESC;
    """

    try:
        results = client.query(query).result()
        rows = list(results)
    except Exception as e:
        print(f"Error executing BigQuery query: {e}")
        return

    if not rows:
        print(f"No trades found in the last {hours} hours.")
        return
        
    # Write to CSV
    headers = ["timestamp", "ticker", "BUY/SELL", "Signal", "AI score", "Sent", "RSI", "Vlty", "F-Score", "Conf", "is_healthy", "price", "status", "AI"]
    
    try:
        with open(output_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for row in rows:
                nyc_time = ""
                if row.timestamp:
                    nyc_time = row.timestamp.astimezone(pytz.timezone('America/New_York')).isoformat()
                    
                writer.writerow([
                    nyc_time,
                    row.ticker,
                    row.BUY_SELL,
                    row.extracted_signal,
                    row.extracted_ai_score,
                    f"{row.Sent:.2f}" if row.Sent is not None else "",
                    f"{row.RSI:.2f}" if row.RSI is not None else "",
                    f"{row.Vlty:.4f}" if row.Vlty is not None else "",
                    row.F_Score,
                    row.Conf,
                    row.is_healthy,
                    f"{row.price:.2f}" if row.price is not None else "",
                    row.status,
                    row.gemini_ai
                ])
        print(f"✅ Successfully exported {len(rows)} trades to {output_file}")
    except Exception as e:
        print(f"Error writing to CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract recent trades to a CSV file.")
    parser.add_argument("--hours", type=int, default=24, help="Number of hours to look back (default: 24)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV filename")
    
    args = parser.parse_args()
    extract_trades(hours=args.hours, output_file=args.output)
