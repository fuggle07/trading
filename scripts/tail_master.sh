#!/bin/bash
# tail_master.sh

export CLOUDSDK_PYTHON_SITEPACKAGES=1

# Capture the first argument
SERVICE_FILTER=$1

if [ -z "$SERVICE_FILTER" ]; then
    echo "--- Initializing Global Firehose (All Services) ---"
    FILTER_STR=""
else
    echo "--- Initializing Tail for Source: $SERVICE_FILTER ---"
    # This matches the service name specifically
    FILTER_STR="resource.labels.service_name=\"$SERVICE_FILTER\""
fi

gcloud beta logging tail "$FILTER_STR" \
  --project=$(gcloud config get-value project) \
  --format="table(timestamp.date('%H:%M:%S'):label=TIME, resource.labels.service_name:label=SOURCE, severity, textPayload:label=MESSAGE)"

