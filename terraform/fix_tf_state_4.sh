#!/bin/bash
export PROJECT_ID="utopian-calling-429014-r9"
echo "Fixing Remaining Logging Metrics..."
METRICS=(
    "paper_equity"
    "sentiment_score"
    "total_cash"
    "market_value"
    "exposure_pct"
    "prediction_confidence"
    "sma_20"
    "sma_50"
    "bb_upper"
    "bb_lower"
    "f_score"
    "conviction"
    "trade_executed"
)

for m in "${METRICS[@]}"; do
    terraform state rm "google_logging_metric.${m}"
    terraform import -var="project_id=${PROJECT_ID}" "google_logging_metric.${m}" "trading/${m}"
done
