#!/bin/bash
# Manual trigger for the trading bot audit cycle
# This forces the bot to run immediately and log fresh data to the dashboard

set -e

echo "🚀 Triggering Trading Bot Audit..."

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe trading-audit-agent \
 --region=us-central1 \
 --format='value(status.url)')

if [ -z "$SERVICE_URL" ]; then
 echo "❌ Failed to get service URL"
 exit 1
fi

echo "📍 Service URL: $SERVICE_URL"

# Get auth token
TOKEN=$(gcloud auth print-identity-token)

# Trigger the audit endpoint
echo "📡 Sending POST request to /run-audit..."
RESPONSE=$(curl -s -X POST "${SERVICE_URL}/run-audit" \
 -H "Authorization: Bearer ${TOKEN}" \
 -H "Content-Type: application/json" \
 -o /tmp/bot_response.txt \
 -w "%{http_code}")

HTTP_CODE="$RESPONSE"
BODY=$(cat /tmp/bot_response.txt)
rm -f /tmp/bot_response.txt

echo ""
echo "📊 Response Code: $HTTP_CODE"
echo "📄 Response Body:"
echo "$BODY"

if [ "$HTTP_CODE" = "200" ]; then
 echo ""
 echo "✅ SUCCESS: Bot audit completed"
 echo "👉 Check your dashboard - it should show updated equity within 1-2 minutes"
else
 echo ""
 echo "⚠️ WARNING: Unexpected response code"
 echo "Check Cloud Run logs for details"
fi
