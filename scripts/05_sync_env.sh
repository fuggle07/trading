#!/bin/bash
# Video: [Automating Env Var Sync](https://www.youtube.com/watch?v=5aOF-RIZS5c)

echo "--- SYNCING LOCAL ENVIRONMENT ---"

# 1. Read from env.yaml and export to .env
if [ -f "env.yaml" ]; then
    # Simple YAML-to-ENV parser
    sed 's/: /=/g' env.yaml > .env
    echo "✅ Local .env generated from env.yaml"
else
    echo "❌ env.yaml not found."
fi

# 2. Verify mandatory GCP Vars
if [ -z "$PROJECT_ID" ]; then
    export PROJECT_ID=$(gcloud config get-value project)
    echo "export PROJECT_ID=$PROJECT_ID" >> .env
fi

echo "--- SYNC COMPLETE ---"

