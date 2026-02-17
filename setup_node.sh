#!/bin/bash
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

# 2.5. Check for schedulers
echo "--- 🔍 STEP 2.5: CHECKING FOR UNMANAGED SCHEDULERS ---"
EXISTING_JOBS=$(gcloud scheduler jobs list --location=$REGION --format="value(ID)")
for job in $EXISTING_JOBS; do
  if [[ ! $job == trading-trigger-* ]]; then
    echo "⚠️  WARNING: Unmanaged job found: $job. Consider deleting manually."
  fi
done

# 3. INFRASTRUCTURE PHASE A (Foundations)
# --- 🏗️  PHASE A: Deploying Foundations ---
# We use -target to ensure the repository exists before we try to push checking
# But first, we need to handle potential state conflicts if resources already exist
echo "--- 🏗️  PHASE A: Deploying Foundations ---"
cd terraform

# Attempt to import existing repository if it exists but isn't in state
if gcloud artifacts repositories describe trading-node-repo --location=us-central1 --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "📦 Repository exists, importing into Terraform state..."
    terraform import -var="project_id=$PROJECT_ID" google_artifact_registry_repository.repo projects/$PROJECT_ID/locations/us-central1/repositories/trading-node-repo || true
fi

# Attempt to import Secret Manager Secrets
for secret in APIFY_TOKEN FINNHUB_KEY IBKR_KEY; do
    if gcloud secrets describe $secret --project=$PROJECT_ID > /dev/null 2>&1; then
         echo "🔐 Secret $secret exists, importing..."
         terraform import -var="project_id=$PROJECT_ID" "google_secret_manager_secret.secrets[\"$secret\"]" projects/$PROJECT_ID/secrets/$secret || true
    fi
done

# Attempt to import Service Account
if gcloud iam service-accounts describe trading-bot-executor@$PROJECT_ID.iam.gserviceaccount.com --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "🤖 Service Account exists, importing..."
    terraform import -var="project_id=$PROJECT_ID" google_service_account.bot_sa projects/$PROJECT_ID/serviceAccounts/trading-bot-executor@$PROJECT_ID.iam.gserviceaccount.com || true
fi

# Attempt to import existing dataset if it exists
if bq show --project_id=$PROJECT_ID system_logs > /dev/null 2>&1; then
    echo "📊 Dataset system_logs exists, importing..."
    terraform import -var="project_id=$PROJECT_ID" google_bigquery_dataset.system_logs projects/$PROJECT_ID/datasets/system_logs || true
fi

if bq show --project_id=$PROJECT_ID trading_data > /dev/null 2>&1; then
    echo "📊 Dataset trading_data exists, importing..."
    terraform import -var="project_id=$PROJECT_ID" google_bigquery_dataset.trading_data projects/$PROJECT_ID/datasets/trading_data || true
fi

# Attempt to import table performance_logs
if bq show --project_id=$PROJECT_ID trading_data.performance_logs > /dev/null 2>&1; then
    echo "📊 Table performance_logs exists, importing..."
    terraform import -var="project_id=$PROJECT_ID" google_bigquery_table.performance_logs projects/$PROJECT_ID/datasets/trading_data/tables/performance_logs || true
fi

# Attempt to import Cloud Run Service
if gcloud run services describe trading-audit-agent --region=us-central1 --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "🚀 Cloud Run Service exists, importing..."
    terraform import -var="project_id=$PROJECT_ID" google_cloud_run_v2_service.trading_bot projects/$PROJECT_ID/locations/us-central1/services/trading-audit-agent || true
fi

# Attempt to import Cloud Scheduler Job
if gcloud scheduler jobs describe trading-trigger-nasdaq --location=us-central1 --project=$PROJECT_ID > /dev/null 2>&1; then
    echo "⏰ Scheduler Job exists, importing..."
    terraform import -var="project_id=$PROJECT_ID" google_cloud_scheduler_job.nasdaq_trigger projects/$PROJECT_ID/locations/us-central1/jobs/trading-trigger-nasdaq || true
fi

terraform init
# We target the repo and the logging infrastructure first
terraform apply \
  -target=google_artifact_registry_repository.repo \
  -target=google_bigquery_dataset.system_logs \
  -target=google_logging_project_bucket_config.audit_log_bucket \
  -var="project_id=$PROJECT_ID" -auto-approve
cd ..

# 4. SOFTWARE PHASE (Force Rebuild & Push)
echo "--- 📦 PHASE B: Building and Pushing Docker Image (Force Refresh) ---"
cd bot
# Use Cloud Build instead of local docker
gcloud builds submit --tag us-central1-docker.pkg.dev/$PROJECT_ID/trading-node-repo/trading-bot:latest .
cd ..
# 5. INFRASTRUCTURE PHASE B (Compute & Orchestration)
echo "--- ⚙️  PHASE C: Finalizing Infrastructure & Forcing Rollout ---"
cd terraform
# We inject a DEPLOY_TIME timestamp via terraform variable to force a Cloud Run revision
# Note: Ensure your terraform main.tf handles a 'deploy_time' variable or uses it in env vars
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="deploy_time=$(date +%s)" \
  -auto-approve
cd ..

# 6. POST-DEPLOYMENT SYNC
if [ -f "./scripts/05_sync_env.sh" ]; then
    ./scripts/05_sync_env.sh
fi

echo "--- ✅ DEPLOYMENT COMPLETE: ABERFELDIE NODE IS SECURE & LIVE ---"
# Final sanity check: Output the dashboard link
cd terraform && terraform output dashboard_url && cd ..