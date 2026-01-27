#!/bin/bash
# Reference: [GCP IAM Best Practices](https://cloud.google.com/iam/docs/using-iam-securely)
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="trading-bot-executor@${PROJECT_ID}.iam.gserviceaccount.com"
ROLES=("roles/secretmanager.secretAccessor" "roles/aiplatform.user" "roles/logging.logWriter")

for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SA_EMAIL" --role="$ROLE" --quiet
done

