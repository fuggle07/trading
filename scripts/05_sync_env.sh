
#!/bin/bash
# scripts/05_sync_env.sh
# Directive: Synchronize High-Resolution environmental parameters.
# Reference: [GCP Environment Variable Best Practices](https://cloud.google.com/functions/docs/configuring/env-var)

set -e # Exit on error

echo "--- 📋 ABERFELDIE NODE: ENVIRONMENT SYNCHRONIZATION ---"

# 1. Path Resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_YAML="$SCRIPT_DIR/../env.yaml"
DOT_ENV="$SCRIPT_DIR/../.env"

# 2. Define Mandatory Parameters (The "Surgical Baseline")
# These are the variables required for the VIX, Tax, and Hurdle logic.
PROJECT_ID=$(gcloud config get-value project)
BASE_TICKERS="NVDA,MU,TSLA,AMD,PLTR,COIN,META,MSTR"
VIX_THRESHOLD_HIGH="30.0"
VOLATILITY_SENSITIVITY="1.0"
MORTGAGE_HURDLE_RATE="0.054" # 5.4%
CAPITAL_USD="50000.0" # Your potential offset withdrawal
MIN_EDGE_THRESHOLD="0.015" # 1.5% minimum predicted gain to override brokerage drag
MIN_EXPOSURE_THRESHOLD="0.65" # 65% target exposure

# 3. Construct/Update env.yaml
# We use a heredoc to ensure clean YAML formatting for GCP.
echo "📝 Updating env.yaml with financial parameters..."
cat <<EOF > "$ENV_YAML"
PROJECT_ID: "$PROJECT_ID"
BASE_TICKERS: "$BASE_TICKERS"
VIX_THRESHOLD_HIGH: "$VIX_THRESHOLD_HIGH"
VOLATILITY_SENSITIVITY: "$VOLATILITY_SENSITIVITY"
MORTGAGE_HURDLE_RATE: "$MORTGAGE_HURDLE_RATE"
CAPITAL_USD: "$CAPITAL_USD"
MIN_EDGE_THRESHOLD: "$MIN_EDGE_THRESHOLD"
MIN_EXPOSURE_THRESHOLD: "$MIN_EXPOSURE_THRESHOLD"
EOF

# 4. Generate Local .env for Development
# Uses a surgical sed command to convert YAML to ENV format for local testing.
if [ -f "$ENV_YAML" ]; then
 sed 's/: /=/g' "$ENV_YAML" | tr -d '"' > "$DOT_ENV"
 echo "✅ Local .env generated for workstation testing."
else
 echo "❌ ERROR: env.yaml could not be generated."
 exit 1
fi

echo "--- ✨ ENVIRONMENT READY: Node is configured for tax and hurdle audits ---"
