#!/bin/bash
# setup_node.sh - Master Orchestrator v4.2 (Aberfeldie Secure Edition)
set -e

# 0. SECURITY MASKING
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
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
REPO_NAME="trading-node-repo"
IMAGE_NAME="trading-bot"
FULL_IMAGE_PATH="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:latest"

echo "--- 🚀 STARTING SECURE DEPLOYMENT FOR PROJECT: $PROJECT_ID ---"

# 2. AUTH CHECK
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

# 3. INFRASTRUCTURE PHASE A (Foundations)
echo "--- 🏗️  PHASE A: Deploying Foundations ---"
cd terraform
terraform init
# We target the repo and the logging infrastructure first
terraform apply \
  -target=google_artifact_registry_repository.repo \
  -target=google_bigquery_dataset.system_logs \
  -target=google_logging_project_bucket_config.audit_log_bucket \
  -var="project_id=$PROJECT_ID" -auto-approve
cd ..

# 4. SOFTWARE PHASE (Build & Push)
echo "--- 📦 PHASE B: Building and Pushing Docker Image ---"
# Ensure your context (./) includes requirements.txt and all agent files
pushd bot
docker build -t "$FULL_IMAGE_PATH" .
docker push "$FULL_IMAGE_PATH"
popd

# 5. INFRASTRUCTURE PHASE B (Compute & Orchestration)
echo "--- ⚙️  PHASE C: Finalizing Infrastructure ---"
cd terraform
terraform apply -var="project_id=$PROJECT_ID" -auto-approve
cd ..

# 6. POST-DEPLOYMENT SYNC
# Ensure these scripts are executable: chmod +x scripts/*.sh
if [ -f "./scripts/05_sync_env.sh" ]; then
    ./scripts/05_sync_env.sh
fi

echo "--- ✅ DEPLOYMENT COMPLETE: ABERFELDIE NODE IS SECURE & LIVE ---"
