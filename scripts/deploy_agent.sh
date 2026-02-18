
#!/bin/bash
# deploy_agent.sh - Automation Script for GCP Cloud Functions

# 1. Configuration
PROJECT_ID="your-project-id"
REGION="us-central1"
FUNCTION_NAME="trading-audit-agent"
ENTRY_POINT="run_audit" # The function name inside your agent.py

# 2. Package the dependencies
# Ensure you have a requirements.txt with: google-cloud-secret-manager, vertexai, ccxt
echo "Packaging 'Surgical' Agent..."
zip -r function_source.zip agent.py requirements.txt

# 3. Push to GCP Cloud Functions (2nd Gen)
# Video: [Cloud Functions 2nd Gen Deployment](https://www.youtube.com/watch?v=5aOF-RIZS5c)
gcloud functions deploy $FUNCTION_NAME \
 --gen2 \
 --runtime=python314 \
 --region=$REGION \
 --source=. \
 --entry-point=$ENTRY_POINT \
 --trigger-http \
 --allow-unauthenticated # In production, use --no-allow-unauthenticated for safety
