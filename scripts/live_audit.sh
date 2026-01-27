#!/bin/bash
# scripts/live_audit.sh
# Directive: Trigger a concurrent audit and open the 'Thought Stream' in-browser.

set -euo pipefail

echo "--- 🛰️  ABERFELDIE NODE: LIVE AUDIT TRIGGER ---"

# 1. Extract Function URL
REGION="us-central1"
SERVICE_NAME="trading-audit-agent"
PROJECT_ID=$(gcloud config get-value project)

FUNCTION_URL=$(gcloud functions describe $SERVICE_NAME \
  --region=$REGION --format="value(serviceConfig.uri)")

# 2. Trigger Audit (Authenticated)
echo "🚀 Dispatching Audit to: $FUNCTION_URL"
curl -s -m 60 -X POST "$FUNCTION_URL" \
  -H "Authorization: bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"action": "audit"}' > /dev/null &

# 3. Construct Surgical Logs URL
# Filter logic: Cloud Run Revision + Service Name + Last 1 hour
ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('resource.type=\"cloud_run_revision\"\nresource.labels.service_name=\"$SERVICE_NAME\"\nseverity>=INFO'))")
LOGS_URL="https://console.cloud.google.com/logs/query;query=$ENCODED_QUERY?project=$PROJECT_ID"

# 4. Open Browser (Ubuntu/Debian standard)
echo "🖥️  Opening Logs Explorer in browser..."
if command -v xdg-open &> /dev/null; then
    xdg-open "$LOGS_URL"
elif command -v open &> /dev/null; then
    open "$LOGS_URL"
else
    echo "⚠️  Browser trigger failed. Manually visit: $LOGS_URL"
fi

echo "--- ✨ AUDIT RUNNING IN BACKGROUND. WATCH THE LOGS. ---"

