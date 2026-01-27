#!/bin/bash
# setup_node.sh - Version 2.3 (Full Restoration)
# Location: /home/peterf/trading_node/setup_node.sh

set -e

echo "--- 🛠️  ABERFELDIE NODE: STARTING FULL INITIALIZATION ---"

# --- STEP -2: SECURITY MASKING ---
echo "[Step -2] Regenerating Security Masks..."

# 1. Root .gitignore
cat <<EOF > .gitignore
.env
env.yaml
secrets.json
*.pem
*.key
*.p12
terraform/.terraform/
*.tfstate
__pycache__/
.venv/
.DS_Store
EOF

# 2. Root .gcloudignore (Active Directive)
cat <<EOF > .gcloudignore
# .gcloudignore: Inherit rules from .gitignore
#!include:.gitignore

# Explicit GCP Deployment Exclusions
.git/
.gitignore
.gcloudignore
terraform/
scripts/
blueprint.md
references.md
EOF
echo "✅ Security masks verified."

# --- STEP -1: DEPENDENCY AUDIT ---
echo "[Step -1] Auditing Local Environment (Ubuntu)..."

# Idempotent check for gcloud and terraform
if ! command -v gcloud &> /dev/null || ! command -v terraform &> /dev/null; then
    echo "⚠️  Missing core tools. Executing dependency actuator..."
    chmod +x ./scripts/install_dependencies.sh
    ./scripts/install_dependencies.sh
    
    # Surgical PATH update for the current shell session
    export PATH="$HOME/.tfenv/bin:$PATH"
    if command -v tfenv &> /dev/null; then
        eval "$(tfenv init -)"
    fi
else
    echo "✅ System tools (gcloud, tfenv) verified."
fi

# --- STEP 0: SYNC LOGISTICS ---
echo "[Step 0] Syncing Environment Variables..."
./scripts/05_sync_env.sh

# --- STEP 1: DEPLOY HARDWARE ---
echo "[Step 1] Initializing GCP Infrastructure..."
(cd terraform && terraform init && terraform apply -auto-approve)

# --- REMAINING STEPS ---
./scripts/02_harden_iam.sh
./scripts/03_sync_secrets.sh
./scripts/04_deploy_bot.sh

echo "--- ✨ SYSTEM INITIALIZATION SUCCESSFUL ---"

