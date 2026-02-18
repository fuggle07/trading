import logging
import os
import sys
import json
from datetime import datetime
import pytz

# 1. STRUCTURED LOGGING CONFIGURATION
class CloudLoggingFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "component": os.getenv("K_SERVICE", "trading-bot"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": getattr(record, "event", "GENERIC"),
            "details": getattr(record, "details", {}),
        }
        return json.dumps(log_entry)

# Setup the master logger to use stdout (Cloud Run standard)
logger = logging.getLogger("master-log")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(CloudLoggingFormatter())
logger.addHandler(handler)

# 2. MASTER LOGGING INTERFACE

def log_audit(level, message, extra=None):
    # This format is automatically parsed by Google Cloud Logging
    entry = {"severity": level, "message": message, "extra": extra or {}}
    print(json.dumps(entry))
    sys.stdout.flush()  # Force the log out immediately

# 3. BIGQUERY TELEMETRY

def log_watchlist_data(client, table_id, ticker, price, sentiment=None, confidence=0):
    """
    Ensures the JSON keys perfectly match the BigQuery schema.
    """
    row_to_insert = [
        {
            "timestamp": datetime.now(pytz.utc).isoformat(),
            "ticker": ticker,
            "price": float(price),
            "sentiment_score": float(sentiment) if sentiment is not None else 0.0,
        }
    ]

    try:
        errors = client.insert_rows_json(table_id, row_to_insert)
        if errors == []:
            # Structured Log for Metric Extraction
            log_payload = {
                "message": f"✅ Telemetry: Logged {ticker} at {price}",
                "ticker": ticker,
                "price": float(price),
                "sentiment_score": float(sentiment) if sentiment is not None else 0.0,
                "prediction_confidence": int(confidence or 0),
                "event": "WATCHLIST_LOG",
            }
            print(json.dumps(log_payload))
        else:
            print(f"❌ BQ ERROR: {errors}")
            raise RuntimeError(f"Sync failed: {errors}")
    except Exception as e:
        print(f"🔥 Critical Telemetry Failure: {e}")

def log_performance(client, table_id, metrics):
    """
    Logs performance metrics (Total Equity) to BigQuery.
    """
    total_equity = float(metrics.get("total_equity", 0.0))
    total_cash = float(metrics.get("total_cash", 0.0))
    total_market_value = float(metrics.get("total_market_value", 0.0))
    exposure = total_market_value / total_equity if total_equity > 0 else 0.0

    row = {
        "timestamp": datetime.now(pytz.utc).isoformat(),
        "paper_equity": total_equity,
        "tax_buffer_usd": 0.0,
        "fx_rate_aud": 1.0,
        "daily_hurdle_aud": 0.0,
        "net_alpha_usd": 0.0,
        "node_id": os.getenv("K_SERVICE", "local-bot"),
        "recommendation": "HOLD",
    }

    try:
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            print(f"❌ Performance Log Error: {errors}")
        else:
            # Structured Log for Metric Extraction
            log_payload = {
                "message": f"📈 Logged Performance: ${total_equity:.2f}",
                "paper_equity": total_equity,
                "total_cash": total_cash,
                "total_market_value": total_market_value,
                "exposure_pct": exposure * 100.0,
                "node_id": os.getenv("K_SERVICE", "local-bot"),
                "event": "PERFORMANCE_LOG",
            }
            print(json.dumps(log_payload))
    except Exception as e:
        print(f"🔥 Performance Log Failure: {e}")

def log_decision(ticker, action, reason, details=None):
    """
    High-visibility logging for trading decisions (BUY, SELL, SKIP).
    Priority: Terminal readability for tailing logs.
    """
    emoji = "🚀" if action == "BUY" else "🛑" if action == "SELL" else "⏭️"
    message = f"[DECISION] {emoji} {action} {ticker}: {reason}"
    
    # console output for tailing
    print(f"\n{message}")
    if details:
        print(f"           Details: {details}")
    
    # Structured log for Cloud Logging
    log_payload = {
        "severity": "INFO",
        "message": message,
        "ticker": ticker,
        "action": action,
        "reason": reason,
        "details": details or {},
        "event": "TRADING_DECISION",
    }
    print(json.dumps(log_payload))
    sys.stdout.flush()
