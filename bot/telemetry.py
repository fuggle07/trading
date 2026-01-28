import os
import logging
from google.cloud import bigquery
from datetime import datetime, timezone

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "utopian-calling-429014-r9")
DATASET_ID = "trading_data"
TABLE_ID = "performance_logs"

# Constants for the Aberfeldie Node
HOME_LOAN_RATE = 0.052  # 5.2% Hurdle (Opportunity Cost)
TAX_RESERVE_RATE = 0.30 # 30% CGT Reserve (Australia)
INITIAL_CAPITAL_USD = 50000.0

# Initialize BigQuery Client
client = bigquery.Client()

def log_watchlist_data(ticker, price, sentiment=None):
    client = bigquery.Client()
    table_id = "utopian-calling-429014-r9.trading_data.watchlist_logs"
    
    # The keys here MUST match the BigQuery column names exactly
    rows_to_insert = [{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "price": float(price),
        "sentiment_score": float(sentiment) if sentiment else None
    }]
    
    errors = client.insert_rows_json(table_id, rows_to_insert)
    
    if errors:
        print(f"❌ BigQuery Watchlist Insert Error for {ticker}: {errors}")
    else:
        print(f"✅ Logged {ticker} to watchlist.")

def log_performance(paper_equity, fx_rate_aud):
    """
    Surgically calculates tax and hurdle metrics before logging to BigQuery.
    
    Args:
        paper_equity (float): Current total account value in USD.
        fx_rate_aud (float): Current AUD/USD spot rate.
    """
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # 1. TAX TELEMETRY (30% on Profit)
    profit_usd = max(0, paper_equity - INITIAL_CAPITAL_USD)
    tax_buffer_usd = profit_usd * TAX_RESERVE_RATE
    
    # 2. HURDLE TELEMETRY (Daily interest cost of $50k loan)
    # daily_hurdle = (Principal * Rate) / 365
    daily_hurdle_aud = (INITIAL_CAPITAL_USD * fx_rate_aud * HOME_LOAN_RATE) / 365
    
    # 3. NET ALPHA (USD)
    # Calculation: (Post-Tax Profit) - (Daily Hurdle converted to USD)
    net_alpha_usd = (profit_usd - tax_buffer_usd) - (daily_hurdle_aud / fx_rate_aud)

    # 4. PREPARE BIGQUERY PAYLOAD
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_equity": float(paper_equity),
        "tax_buffer_usd": float(tax_buffer_usd),
        "fx_rate_aud": float(fx_rate_aud),
        "daily_hurdle_aud": float(daily_hurdle_aud),
        "net_alpha_usd": float(net_alpha_usd),
        "node_id": "aberfeldie-01",
        "recommendation": "✅ HOLD" if net_alpha_usd > 0 else "⚠️ LIQUIDATE_TO_OFFSET"
    }

    # 5. LOG TO CLOUD LOGGING (For visibility in 'gcloud logs tail')
    logging.info(f"AUDIT DATA: Net Alpha ${net_alpha_usd:.2f} USD | "
                 f"Daily Hurdle ${daily_hurdle_aud:.2f} AUD | "
                 f"Tax Buffer ${tax_buffer_usd:.2f} USD")

    # 6. EXECUTE BIGQUERY INSERTION
    try:
        errors = client.insert_rows_json(table_ref, [row])
        if errors:
            logging.error(f"BigQuery Insert Errors: {errors}")
        else:
            logging.info("Audit successfully streamed to BigQuery.")
        return row
    except Exception as e:
        logging.error(f"Telemetry Actuation Failed: {e}")
        return None

def log_watchlist_data(ticker, price):
    """Logs individual stock prices to the watchlist_logs table."""
    client = bigquery.Client()
    table_id = f"{PROJECT_ID}.trading_data.watchlist_logs"

    rows_to_insert = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "price": float(price)
        }
    ]

    errors = client.insert_rows_json(table_id, rows_to_insert)
    if errors:
        print(f"❌ Watchlist Insert Error for {ticker}: {errors}")
    else:
        print(f"✅ Watchlist Sync: {ticker} @ ${price}")

