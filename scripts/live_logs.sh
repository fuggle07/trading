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
# Filter for logs that actually have content to display (avoiding empty lines)
FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND (textPayload:* OR jsonPayload.message:*)"

echo "📡 Tailing logs for $SERVICE_NAME..."
echo "💡 Tip: Use 'live_logs.sh | grep DECISION' to isolate trading actions."

# Check arguments for output mode
OUTPUT_MODE="text"
if [[ "$1" == "--json" ]] || [[ "$1" == "--raw" ]]; then
  OUTPUT_MODE="json"
  echo "🔍 JSON Mode: Outputting raw JSON..."
else
  echo "📝 Text Mode: Formatting logs (Use --json for raw output)..."
fi

# Check if "beta" component is installed (required for logging tail)
if ! gcloud components list --filter="id=beta AND state.name=Installed" --format="value(id)" | grep -q beta; then
  echo "📦 Installing required 'beta' component for gcloud..."
  gcloud components install beta --quiet
fi

# 1. Fetch recent logs first (Immediate Feedback)
echo "📜 Fetching last 10 logs..."

if [[ "$OUTPUT_MODE" == "json" ]]; then
  gcloud logging read "$FILTER" --project "$PROJECT_ID" --limit=10 --order=desc --format=json | jq 'reverse | .[]'
else
  gcloud logging read "$FILTER" --project "$PROJECT_ID" --limit=10 --order=desc --format=json | \
    jq -r 'reverse | .[] | .textPayload // .jsonPayload.message // empty'
fi

echo "🔴 Switching to LIVE TAIL..."

# 2. Stream live logs (Unbuffered)
echo "🔍 Debug Mode: Raw JSON output (to rule out jq buffering)..."
export PYTHONUNBUFFERED=1

if [[ "$OUTPUT_MODE" == "json" ]]; then
  gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format=json
else
  # Use Go-template to coalesce fields cleanly without internal tabs or external pipes
  gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" \
  --format='template({{if .textPayload}}{{.textPayload}}{{else}}{{.jsonPayload.message}}{{end}})'
fi
