#!/bin/bash
# live_logs.sh
# Streams live logs from the Cloud Run service.

PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="trading-audit-agent"
REGION="us-central1"

echo "📡 Streaming logs from $SERVICE_NAME ($REGION)..."
echo "Press Ctrl+C to stop."

# We use gcloud logging tail which is more stable than the beta run command.
# Captures BOTH textPayload and structured jsonPayload.message
# IMPORTANT: If you pipe this, use 'grep --line-buffered' to avoid output delays.
# Avoid using 'tail' or 'head' on the end of a live stream.

FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\""

echo "📡 Tailing logs for $SERVICE_NAME..."
echo "💡 Tip: Use 'live_logs.sh | grep DECISION' to isolate trading actions."
# Check if "beta" component is installed (required for logging tail)
if ! gcloud components list --filter="id=beta AND state.name=Installed" --format="value(id)" | grep -q beta; then
  echo "📦 Installing required 'beta' component for gcloud..."
  gcloud components install beta --quiet
fi

# 1. Fetch recent logs first (Immediate Feedback)
echo "📜 Fetching last 10 logs..."
gcloud logging read "$FILTER" --project "$PROJECT_ID" --limit=10 --order=asc --format=json | \
  jq -r '.[] | .textPayload // .jsonPayload.message // empty'

echo "🔴 Switching to LIVE TAIL..."

# 2. Stream live logs (Unbuffered)
export PYTHONUNBUFFERED=1
gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format=json | \
  jq -r --unbuffered '.textPayload // .jsonPayload.message // empty'
