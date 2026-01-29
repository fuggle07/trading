#!/bin/bash
# Deployment script with runtime mortgage rate configuration
PROJECT_ID=$(gcloud config get-value project)
MORTGAGE_RATE=0.0625  # Set your target rate here

echo "Deploying Trading Bot to Cloud Run with rate: $MORTGAGE_RATE"

gcloud builds submit --tag gcr.io/$PROJECT_ID/trading-bot bot/

gcloud run deploy trading-bot \
  --image gcr.io/$PROJECT_ID/trading-bot \
  --platform managed \
  --region australia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,MORTGAGE_RATE=$MORTGAGE_RATE"

