# live_logs.sh
# Streams live logs from the Cloud Run service.

usage() {
  echo "Usage: ./utilities/live_logs.sh [OPTIONS]"
  echo "Options:"
  echo "  --json, --raw    Output raw JSON logs"
  echo "  --help           Show this help message"
  exit 1
}

if [[ "$1" == "--help" ]]; then
  usage
fi

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

# 1. Fetch recent logs message
# (Disabled as requested)

echo "🔴 Switching to LIVE TAIL..."

# 2. Stream live logs (Unbuffered)
echo "🔍 Debug Mode: Raw JSON output (to rule out jq buffering)..."
export PYTHONUNBUFFERED=1

if [[ "$OUTPUT_MODE" == "json" ]]; then
  gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format=json
else
  # Use simple value format and remove internal tabs to avoid indentation issues
  gcloud beta logging tail "$FILTER" --project "$PROJECT_ID" --format="value(textPayload,jsonPayload.message)" | sed 's/\t//g'
fi
