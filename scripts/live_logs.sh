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
gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format="value(textPayload,jsonPayload.message)"
