
#!/bin/bash
# scripts/01_deploy_infra.sh
# Directive: Provision unified infrastructure for the Aberfeldie Node.
# Video Reference: [GCP Terraform Quickstart 2026](https://www.youtube.com/watch?v=ypFG006G4WQ)

set -e # Exit immediately if a command exits with a non-zero status.

echo "--- 🏗️ ABERFELDIE NODE: INFRASTRUCTURE DEPLOYMENT ---"

# 1. Dependency Check
if ! command -v terraform &> /dev/null; then
 echo "❌ ERROR: 'terraform' is not installed or not in PATH."
 if command -v brew &> /dev/null; then
 echo "💡 Tip: Run 'brew install tfenv && tfenv install 1.10.5 && tfenv use 1.10.5' to install it."
 else
 echo "💡 Tip: Install tfenv (https://github.com/tfutils/tfenv) or Terraform manually."
 fi
 exit 1
fi

# 2. Navigate to the Hardware Tier
# Ensures the script works regardless of where it's called from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

# 4. Build & Push Container
echo "🐳 Building and Pushing Docker Container..."
# Get the Project ID from the environment or tfvars if possible, or assume explicit
# Since this is a script, we can rely on gcloud config or pass it in.
# For simplicity in this environment, we use 'gcloud builds submit' which handles the build and push to GCR/GAR.

# We need to be in the root of the repo
cd "$SCRIPT_DIR/.."
echo "📂 Current Directory: $(pwd)"

# CRITICAL FIX: Remove the stale Dockerfile inside bot/ which flattens the structure
if [ -f "bot/Dockerfile" ]; then
    echo "🗑️ Removing stale bot/Dockerfile to avoid build confusion..."
    rm bot/Dockerfile
fi

ls -la Dockerfile

# Explicitly use the dot as source first, and specify the file
gcloud builds submit . --tag us-central1-docker.pkg.dev/utopian-calling-429014-r9/trading-node-repo/trading-bot:latest

# 5. Infrastructure Deployment
echo "📂 Navigating to: $TERRAFORM_DIR"
cd "$TERRAFORM_DIR" || { echo "❌ ERROR: Terraform directory not found at $TERRAFORM_DIR"; exit 1; }

echo "🔄 Initializing Terraform Providers..."
terraform init

echo "🚀 Applying Infrastructure Blueprint..."
# Get Project ID from gcloud if not set
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project)
fi

# We force a revision update by passing a new timestamp
terraform apply -auto-approve \
    -var="project_id=$PROJECT_ID" \
    -var="deploy_time=$(date +%s)"

echo "✅ INFRASTRUCTURE READY: Project shells and analytics tier provisioned."
