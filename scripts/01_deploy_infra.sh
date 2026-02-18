
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

echo "📂 Navigating to: $TERRAFORM_DIR"
cd "$TERRAFORM_DIR" || { echo "❌ ERROR: Terraform directory not found at $TERRAFORM_DIR"; exit 1; }

# 3. Validation Gate
if [ ! -f "main.tf" ]; then
 echo "❌ ERROR: main.tf not found in $(pwd). Deployment aborted."
 exit 1
fi

# 4. Initialization & Execution
echo "🔄 Initializing Terraform Providers..."
terraform init

echo "🚀 Applying Infrastructure Blueprint..."
# Note: This will now create the unified BigQuery schema with FX and Hurdle fields.
terraform apply -auto-approve

echo "✅ INFRASTRUCTURE READY: Project shells and analytics tier provisioned."
