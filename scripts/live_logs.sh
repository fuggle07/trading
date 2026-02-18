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

# Check arguments for output mode
OUTPUT_MODE="text"
if [[ "$1" == "--json" ]] || [[ "$1" == "--raw" ]]; then
  OUTPUT_MODE="json"
  echo "🔍 JSON Mode: Outputting raw JSON..."
else
  echo "📝 Text Mode: Formatting logs (Use --json for raw output)..."
fi

# 1. Fetch recent logs message
echo "📜 Fetching last 10 logs..."

if [[ "$OUTPUT_MODE" == "json" ]]; then
  gcloud logging read "$FILTER" --project "$PROJECT_ID" --limit=10 --order=desc --format=json | jq 'reverse | .[]'
else
  gcloud logging read "$FILTER" --project "$PROJECT_ID" --limit=10 --order=desc --format=json | \
    jq -r 'reverse | .[] | .textPayload // .jsonPayload.message // empty'
fi

echo "🔴 Switching to LIVE TAIL..."

# 2. Stream live logs (Unbuffered)
export PYTHONUNBUFFERED=1

if [[ "$OUTPUT_MODE" == "json" ]]; then
  gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format=json
else
  # Use native gcloud formatting to avoid pipe buffering issues
  gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format="value(textPayload,jsonPayload.message)"
fi
