#!/bin/bash
# scripts/02_harden_iam.sh
# Directive: Enforce Least Privilege for the Aberfeldie Node.
# Reference: [GCP IAM Best Practices](https://cloud.google.com/iam/docs/using-iam-securely)

set -e # Exit on error

echo "--- 🔐 ABERFELDIE NODE: IAM HARDENING ---"

# 1. Identity Resolution
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="trading-bot-executor@${PROJECT_ID}.iam.gserviceaccount.com"

# 2. Surgical Role Definition
# Added roles/bigquery.dataEditor for the telemetry stream.
ROLES=(
    "roles/secretmanager.secretAccessor" # Access Finnhub/IBKR keys
    "roles/aiplatform.user"              # Trigger Vertex AI reasoning
    "roles/logging.logWriter"            # Push structured logs to Logs Explorer
    "roles/bigquery.dataEditor"          # Write performance & tax data to BigQuery
)

# 3. Policy Application
echo "🛡️  Applying least-privilege roles to: $SA_EMAIL"
for ROLE in "${ROLES[@]}"; do
    echo "🔗 Binding $ROLE..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" \
        --condition=None \
        --quiet > /dev/null
done

echo "✅ IDENTITY HARDENED: Service Account restricted to surgical operational roles."

