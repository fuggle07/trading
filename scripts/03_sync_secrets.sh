#!/bin/bash
# scripts/03_sync_secrets.sh
# Directive: Securely inject API keys into GCP Secret Manager.
# Reference: [Managing Secrets with gcloud](https://www.youtube.com/watch?v=EYDLlnmM5x8)

set -e # Exit on error

echo "--- 🔑 ABERFELDIE NODE: SECRET SYNCHRONIZATION ---"
echo "Note: Leave blank and press Enter to skip a specific secret."

# 1. Expanded Secret Manifest
# Added APIFY_TOKEN for 'Public Noise' scraping and sentiment logic.
SECRETS=("FINNHUB_KEY" "IBKR_KEY" "APIFY_TOKEN")

# 2. Secure Injection Loop
for S in "${SECRETS[@]}"; do
    # -s flag prevents the key from being echoed to the terminal/history
    read -rs -p "🔐 Enter value for $S: " VAL
    echo "" # New line for visual clarity

    if [ -n "$VAL" ]; then
        echo "📤 Updating $S in Secret Manager..."
        echo -n "$VAL" | gcloud secrets versions add "$S" --data-file=- --quiet
        echo "✅ $S version updated."
    else
        echo "⏩ Skipping $S (no value provided)."
    fi
done

echo "--- ✨ SECRET SYNC COMPLETE ---"

