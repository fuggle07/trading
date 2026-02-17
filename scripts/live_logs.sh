#!/bin/bash
# live_logs.sh
# Streams live logs from the Cloud Run service.

PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="trading-audit-agent"
REGION="us-central1"

echo "📡 Streaming logs from $SERVICE_NAME ($REGION)..."
echo "Press Ctrl+C to stop."

gcloud beta run services logs tail $SERVICE_NAME \
    --project $PROJECT_ID \
    --region $REGION
