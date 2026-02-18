#!/bin/bash
# live_logs.sh
# Streams live logs from the Cloud Run service.

PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="trading-audit-agent"
REGION="us-central1"

echo "📡 Streaming logs from $SERVICE_NAME ($REGION)..."
echo "Press Ctrl+C to stop."

# We use gcloud logging tail which is more stable than the beta run command.
# Added --format="get(textPayload)" for cleaner output.
# IMPORTANT: If you grep this, use --line-buffered

FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\""

echo "📡 Tailing logs for $SERVICE_NAME..."
echo "💡 Tip: Use 'live_logs.sh | grep DECISION' to see only trading actions."
gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format="get(textPayload)" | grep --line-buffered -E "\[DECISION\]|Deep Health|Fundamental|Filing|🚨|✅|❌"
