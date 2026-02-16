# test_bot.sh - Manual Verification Script
set -e

echo "🔍 Fetching service identity..."
URL=$(gcloud run services describe trading-audit-agent --region us-central1 --format 'value(status.url)')

echo "🚀 Triggering Health Check at $URL/health..."
RESPONSE=$(curl -s -X POST "$URL/health" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)")

echo "🚀 Triggering Manual Audit at $URL/run-audit..."
RESPONSE=$(curl -s -X POST "$URL/run-audit" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)")

echo "📦 Server Response: $RESPONSE"

echo "📊 Checking BigQuery for latest entry..."
bq query --use_legacy_sql=false \
"SELECT timestamp, ticker, price FROM \`$(gcloud config get-value project).trading_data.watchlist_logs\` ORDER BY timestamp DESC LIMIT 1"

