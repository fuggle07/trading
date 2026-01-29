#!/bin/bash
# tail_master.sh

PROJECT_ID=$(gcloud config get-value project)
SERVICE_FILTER=$1

if [ -z "$SERVICE_FILTER" ]; then
    FILTER_STR="resource.type=\"cloud_run_revision\""
else
    FILTER_STR="resource.labels.service_name=\"$SERVICE_FILTER\""
fi

echo "--- Monitoring $PROJECT_ID ---"

LAST_SEEN_ID=""

while true; do
    LOGS=$(gcloud logging read "$FILTER_STR" --limit=10 --format="json" 2>/dev/null)

    echo "$LOGS" | jq -r 'reverse | .[] | 
      "\(.timestamp[11:19]) | " + 
      "\((.resource.labels.service_name // "sys") | .[0:15]) | " + 
      "\((.severity // "LOG") | .[0:4]) | " + 
      "\(.textPayload // .proto_payload.status.message // .jsonPayload.message // .proto_payload.method_name // "---")"' | uniq
    
    sleep 3
done

