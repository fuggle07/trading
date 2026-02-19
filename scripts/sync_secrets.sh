
#!/bin/bash
# sync_secrets.sh - Authenticated Secret Injection
# Directive: Inject values into GCP shells without leaking to history.

# 1. Config: Define the required sensor keys
REQUIRED_SECRETS=("FINNHUB_KEY" "IBKR_KEY" "APIFY_TOKEN" "ALPACA_API_KEY" "ALPACA_API_SECRET" "ALPHA_VANTAGE_KEY" "FMP_KEY")

echo "--- ABERFELDIE NODE: SECRET SYNCHRONIZATION ---"

for SECRET in "${REQUIRED_SECRETS[@]}"; do
 # Check if the secret shell exists in GCP first
 if ! gcloud secrets describe "$SECRET" &>/dev/null; then
 echo "❌ ERROR: Secret shell '$SECRET' not found in GCP. Run Terraform first."
 continue
 fi

 # 2. Silent Input: Capture value without echoing to screen
 read -rs -p "Enter value for $SECRET: " SECRET_VALUE
 echo "" # New line after silent input

 if [ -z "$SECRET_VALUE" ]; then
 echo "⚠️ Skipping $SECRET (no value provided)."
 continue
 fi

 # 3. Injection: Create a new version in Secret Manager
 # We use --data-file=- to read from stdin, avoiding process list leaks.
 echo -n "$SECRET_VALUE" | gcloud secrets versions add "$SECRET" --data-file=- \
 --quiet &>/dev/null

 if [ $? -eq 0 ]; then
 echo "✅ $SECRET: Version updated successfully."
 else
 echo "❌ $SECRET: Injection failed. Check permissions."
 fi
done

echo "--- SYNC COMPLETE ---"
