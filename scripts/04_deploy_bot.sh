#!/bin/bash
# scripts/04_deploy_bot.sh
# Directive: Surgical deployment of the /bot logic tier.

# Resolve the absolute path to the bot directory relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_SOURCE="$SCRIPT_DIR/../bot"

echo "--- 🛰️  DEPLOYING BOT LOGIC FROM: $BOT_SOURCE ---"

# Deploying with 2nd Gen runtime for concurrency support
gcloud functions deploy trading-audit-agent \
  --gen2 \
  --runtime=python313 \
  --region=us-central1 \
  --source="$BOT_SOURCE" \
  --entry-point=main_handler \
  --trigger-http \
  --env-vars-file="$SCRIPT_DIR/../env.yaml" \
  --service-account="trading-bot-executor@$(gcloud config get-value project).iam.gserviceaccount.com" \
  --quiet

echo "--- ✅ DEPLOYMENT COMPLETE ---"

