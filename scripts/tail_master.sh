#!/bin/bash
# tail_master.sh

PROJECT_ID=$(gcloud config get-value project)
SERVICE_FILTER=$1

if [ -z "$SERVICE_FILTER" ]; then
    FILTER_STR="resource.type=\"cloud_run_revision\""
else
    FILTER_STR="resource.labels.service_name=\"$SERVICE_FILTER\""
fi

echo "--- Monitoring $PROJECT_ID (Time-Gated) ---"

# Initialize watermark with the current time in ISO format
LAST_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

while true; do
    # Fetch logs
    LOGS=$(gcloud logging read "$FILTER_STR" --limit=20 --order=desc --format="json" 2>/dev/null)
    
    # Process logs: only select logs newer than our LAST_TIMESTAMP
    # We use reverse to print them in chronological order
    echo "$LOGS" | jq -r --arg last "$LAST_TIMESTAMP" '
      . | reverse | .[] | 
      select(.timestamp > $last) |
      "\(.timestamp[11:19]) | \((.resource.labels.service_name // "sys") | .[0:15]) | \((.severity // "LOG") | .[0:4]) | \(.textPayload // .proto_payload.status.message // .jsonPayload.message // .proto_payload.method_name // "---")"
    '

    # Update the watermark to the timestamp of the most recent log found
    NEW_TS=$(echo "$LOGS" | jq -r '.[0].timestamp // empty')
    if [ ! -z "$NEW_TS" ]; then
        LAST_TIMESTAMP=$NEW_TS
    fi
    
    sleep 3
done

