#!/bin/bash
# scripts/01_deploy_infra.sh
# Directive: Provision unified infrastructure for the Aberfeldie Node.
# Video Reference: [GCP Terraform Quickstart 2026](https://www.youtube.com/watch?v=ypFG006G4WQ)

set -e # Exit immediately if a command exits with a non-zero status.

# Ensure tfenv is in the PATH for this subshell
export PATH="$HOME/.tfenv/bin:$PATH"
if command -v tfenv &> /dev/null; then
    eval "$(tfenv init -)"
fi

echo "--- 🏗️  ABERFELDIE NODE: INFRASTRUCTURE DEPLOYMENT ---"

# 1. Navigate to the Hardware Tier
# Ensures the script works regardless of where it's called from.
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR/../terraform"

# 2. Validation Gate
if [ ! -f "main.tf" ]; then
    echo "❌ ERROR: main.tf not found in $(pwd). Deployment aborted."
    exit 1
fi

# 3. Initialization & Execution
echo "🔄 Initializing Terraform Providers..."
terraform init

echo "🚀 Applying Infrastructure Blueprint..."
# Note: This will now create the unified BigQuery schema with FX and Hurdle fields.
terraform apply -auto-approve

echo "✅ INFRASTRUCTURE READY: Project shells and analytics tier provisioned."

