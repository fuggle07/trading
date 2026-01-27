#!/bin/bash
# setup_node.sh - Version 3.0 (Tax & Hurdle Aware)
# Directive: Full system initialization of the Aberfeldie Node.

set -e # Terminate immediately if any step fails.

echo "--- 🛠️  ABERFELDIE NODE: STARTING FULL INITIALIZATION ---"

# --- STEP -2: SECURITY MASKING ---
# Ensures your "Nuclear Codes" (env.yaml, .env) are never uploaded to GCP.
echo "[Step -2] Regenerating Security Masks..."
cat <<EOF > .gitignore
.env
env.yaml
secrets.json
*.tfstate
__pycache__/
.venv/
EOF

cat <<EOF > .gcloudignore
#!include:.gitignore
.git/
terraform/
scripts/
EOF
echo "✅ Security masks verified."

# --- STEP -1: DEPENDENCY AUDIT ---
# Checks for gcloud and terraform, triggering the installer if missing.
echo "[Step -1] Auditing Local Environment..."
if ! command -v gcloud &> /dev/null || ! command -v terraform &> /dev/null; then
    echo "⚠️  Missing core tools. Executing dependency actuator..."
    chmod +x ./scripts/install_dependencies.sh
    ./scripts/install_dependencies.sh
else
    echo "✅ System tools verified."
fi

# --- STEP 0: SYNC LOGISTICS ---
# Populates env.yaml with your 5.2% mortgage hurdle and capital targets.
echo "[Step 0] Syncing Financial Parameters..."
chmod +x ./scripts/05_sync_env.sh
./scripts/05_sync_env.sh

# --- STEP 1: DEPLOY HARDWARE ---
# Provisions the unified BigQuery table with tax and FX fields.
echo "[Step 1] Initializing Unified Infrastructure Tier..."
chmod +x ./scripts/01_deploy_infra.sh
./scripts/01_deploy_infra.sh

# --- STEP 2: HARDEN IDENTITY ---
# Grants the DataEditor role so the bot can write to your new table.
echo "[Step 2] Hardening IAM & Permissions..."
chmod +x ./scripts/02_harden_iam.sh
./scripts/02_harden_iam.sh

# --- STEP 3: PAYLOAD INJECTION ---
# Securely injects Finnhub, IBKR, and Apify keys.
echo "[Step 3] Synchronizing Secrets..."
chmod +x ./scripts/03_sync_secrets.sh
./scripts/03_sync_secrets.sh

# --- STEP 4: DEPLOY LOGIC ---
# Compiles and deploys the Python 3.13 bot to Cloud Run.
echo "[Step 4] Deploying Logic Tier..."
chmod +x ./scripts/04_deploy_bot.sh
./scripts/04_deploy_bot.sh

echo "--- ✨ SYSTEM INITIALIZATION SUCCESSFUL ---"

