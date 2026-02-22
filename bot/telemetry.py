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
            "timestamp": datetime.now(pytz.utc).isoformat(),
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


def log_macro_snapshot(client, project_id, macro_data: dict):
    """
    Persists one macro context snapshot per audit cycle to BigQuery.
    """
    try:
        indices = macro_data.get("indices", {})
        rates = macro_data.get("rates", {})
        calendar = macro_data.get("calendar", [])

        import json

        row = {
            "timestamp": datetime.now(pytz.utc).isoformat(),
            "vix": float(indices.get("vix", 0) or 0),
            "spy_perf": float(indices.get("spy_perf", 0) or 0),
            "qqq_perf": float(indices.get("qqq_perf", 0) or 0),
            "yield_10y": float(rates.get("10Y", 0) or 0),
            "yield_2y": float(rates.get("2Y", 0) or 0),
            "yield_source": str(rates.get("source", "")),
            "calendar_json": json.dumps(calendar) if calendar else None,
        }
        table_id = f"{project_id}.trading_data.macro_snapshots"
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            print(f"❌ Macro Snapshot BQ Error: {errors}")
        else:
            print(
                f"🌍 Macro Snapshot stored (VIX={row['vix']}, SPY={row['spy_perf']:.2f}%)"
            )
    except Exception as e:
        print(f"⚠️ Macro Snapshot Log Failure: {e}")


def log_watchlist_data(
    client,
    table_id,
    ticker,
    price,
    sentiment=None,
    confidence=0,
    rsi=None,
    sma_20=None,
    sma_50=None,
    bb_upper=None,
    bb_lower=None,
    f_score=None,
    conviction=None,
    gemini_reasoning=None,
):
    """
    Ensures the JSON keys perfectly match the BigQuery schema.
    """
    row_to_insert = [
        {
            "timestamp": datetime.now(pytz.utc).isoformat(),
            "ticker": ticker,
            "price": float(price),
            "sentiment_score": float(sentiment) if sentiment is not None else 0.0,
            "rsi": float(rsi) if rsi is not None else None,
            "sma_20": float(sma_20) if sma_20 is not None else None,
            "sma_50": float(sma_50) if sma_50 is not None else None,
            "bb_upper": float(bb_upper) if bb_upper is not None else None,
            "bb_lower": float(bb_lower) if bb_lower is not None else None,
            "f_score": int(f_score) if f_score is not None else None,
            "conviction": int(conviction) if conviction is not None else None,
            "gemini_reasoning": str(gemini_reasoning) if gemini_reasoning else None,
        }
    ]

    try:
        errors = client.insert_rows_json(table_id, row_to_insert)
        if errors == []:
            # Structured Log for Metric Extraction
            log_payload = {
                "message": f"[{ticker}] ✅ Telemetry: Logged {ticker} at {price}",
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
        "fx_rate_aud": float(metrics.get("fx_multiplier", 1.54)),
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
    emoji = (
        "🚀"
        if "BUY" in action
        else "🛑" if "SELL" in action else "🔄" if "SWAP" in action else "⏭️"
    )
    message = f"[DECISION] {emoji} {action} {ticker}: {reason}"

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
