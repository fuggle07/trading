#!/bin/bash
# scripts/04_deploy_bot.sh
# Directive: Surgical deployment of the unified /bot logic tier.
# Reference: [GCP Cloud Functions Gen 2 Deployment](https://cloud.google.com/functions/docs/deploy)

set -e # Exit on error

echo "--- 🛰️  ABERFELDIE NODE: BOT DEPLOYMENT ---"

# 1. Path & Identity Resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_SOURCE="$SCRIPT_DIR/../bot"
PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT="trading-bot-executor@${PROJECT_ID}.iam.gserviceaccount.com"

# 2. The Linter Gate
# Prevents deploying code with syntax errors that would cause 01:00 AM failures.
echo "🔍 Performing pre-flight logic check..."
python3 -m py_compile "$BOT_SOURCE/main.py"
echo "✅ Logic check passed."

# 3. Execution: Gen 2 Cloud Function Deployment
echo "🚀 Uploading Logic Tier to us-central1..."
gcloud functions deploy trading-audit-agent \
  --gen2 \
  --runtime=python313 \
  --region=us-central1 \
  --source="$BOT_SOURCE" \
  --entry-point=main_handler \
  --trigger-http \
  --allow-unauthenticated=false \
  --service-account="$SERVICE_ACCOUNT" \
  --env-vars-file="$SCRIPT_DIR/../env.yaml" \
  --quiet

echo "--- ✅ DEPLOYMENT COMPLETE: Bot is live and tax-aware ---"

