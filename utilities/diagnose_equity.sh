#!/bin/bash
# Check the latest performance log entries to see what's being logged

echo "🔍 Checking latest performance logs from Cloud Logging..."
echo ""

gcloud logging read \
 'resource.type="cloud_run_revision"
 AND resource.labels.service_name="trading-audit-agent"
 AND jsonPayload.event="PERFORMANCE_LOG"' \
 --limit=5 \
 --format=json \
 --freshness=1h | jq -r '.[] | "\(.timestamp) - Paper Equity: \(.jsonPayload.paper_equity // "N/A")"'

echo ""
echo "---"
echo ""
echo "🔍 Checking portfolio table state..."
echo ""

gcloud auth application-default print-access-token > /dev/null 2>&1
if [ $? -eq 0 ]; then
 bq query --nouse_legacy_sql --format=pretty \
 'SELECT asset_name, cash_balance, holdings, avg_price
 FROM `utopian-calling-429014-r9.trading_data.portfolio`
 ORDER BY asset_name'
else
 echo "⚠️ Cannot query BigQuery - authentication needed"
 echo "Run: gcloud auth application-default login"
fi
