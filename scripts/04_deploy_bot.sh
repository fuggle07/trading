#!/bin/bash
# scripts/04_deploy_bot.sh - Refactored for Cloud Run Compliance
set -e

echo "--- 🛰️  ABERFELDIE NODE: BOT DEPLOYMENT ---"

# 1. Identity Resolution
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
IMAGE_PATH="$REGION-docker.pkg.dev/$PROJECT_ID/trading-node-repo/trading-bot:latest"

# 2. Software Phase: Build & Push (Injecting logic into the registry)
echo "📦 Building and Pushing Docker Image..."
# Note: Ensure you have run 'gcloud auth configure-docker' previously
docker buildx build --load -t "$IMAGE_PATH" ./bot
docker push "$IMAGE_PATH"

# 3. Infrastructure Phase: Deploy via Terraform
echo "🚀 Finalizing Cloud Run Deployment..."
cd terraform
# We use -var to ensure the project ID is passed from the shell environment
terraform apply -var="project_id=$PROJECT_ID" -auto-approve
cd ..

echo "--- ✅ DEPLOYMENT COMPLETE: Aberfeldie Node is live ---"
