#!/bin/bash
# setup_node.sh - Master Orchestrator v4.1 (Aberfeldie Secure Edition)
set -e

# 0. SECURITY MASKING (Enforce .gitignore)
echo "--- 🛡️  STEP 0: ENFORCING SECURITY MASKING ---"
GITIGNORE_PATH=".gitignore"
declare -a PROTECTED_FILES=(
  "terraform/.terraform/"
  "*.tfstate"
  "*.tfstate.backup"
  ".terraform.lock.hcl"
  "env.yaml"
  ".env"
  "secrets.sh"
)

for file in "${PROTECTED_FILES[@]}"; do
  if ! grep -qxF "$file" "$GITIGNORE_PATH" 2>/dev/null; then
    echo "Masking $file..."
    echo "$file" >> "$GITIGNORE_PATH"
  fi
done

# 1. BOOTSTRAP ENVIRONMENT
export PATH="$HOME/.tfenv/bin:$PATH"
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
REPO_NAME="trading-node-repo"
IMAGE_NAME="trading-bot"
FULL_IMAGE_PATH="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:latest"

echo "--- 🚀 STARTING SECURE DEPLOYMENT ---"

# 2. DEPENDENCY & AUTH CHECK
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

# 3. INFRASTRUCTURE PHASE A (Registry & Storage)
echo "Deploying Base Infrastructure..."
cd terraform
terraform init
terraform apply -target=google_artifact_registry_repository.repo -target=google_bigquery_dataset.trading_data -auto-approve
cd ..

# 4. SOFTWARE PHASE (Build & Push)
echo "Building and Pushing Docker Image..."
docker buildx build -t "$FULL_IMAGE_PATH" ./bot --load
docker push "$FULL_IMAGE_PATH"

# 5. INFRASTRUCTURE PHASE B (Compute & Secrets)
echo "Finalizing Infrastructure Deployment..."
cd terraform
terraform apply -auto-approve
cd ..

# 6. SECRET & ENV SYNC
./scripts/03_sync_secrets.sh
./scripts/05_sync_env.sh

echo "--- ✅ DEPLOYMENT COMPLETE: ABERFELDIE NODE IS SECURE & LIVE ---"
