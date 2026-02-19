
#!/bin/bash
# scripts/sanity_test.sh
# Directive: Verify the 'Agentic Thought Stream' is reachable.

echo "--- 🔍 ABERFELDIE NODE: SANITY TEST ---"

# 1. Surgical Extraction of the Trigger URL
# For 2nd Gen, we use the serviceConfig.uri format
FUNCTION_URL=$(gcloud functions describe trading-audit-agent \
 --region=us-central1 \
 --format="value(serviceConfig.uri)")

if [ -z "$FUNCTION_URL" ]; then
 echo "❌ ERROR: Could not retrieve Function URL. Is it deployed?"
 exit 1
fi

echo "✅ Target URL: $FUNCTION_URL"

# 2. Trigger the Audit with Authentication
# Note: Since we hardened IAM, we must pass an identity token
echo "🚀 Triggering Concurrent Nasdaq Audit..."
curl -m 60 -X POST "$FUNCTION_URL" \
 -H "Authorization: bearer $(gcloud auth print-identity-token)" \
 -H "Content-Type: application/json" \
 -d '{"action": "audit"}'

echo -e "\n--- ✨ TEST COMPLETE. CHECK CLOUD LOGS FOR RESULTS ---"
