#!/bin/bash
# Video: [Managing Secrets with gcloud](https://www.youtube.com/watch?v=EYDLlnmM5x8)
SECRETS=("FINNHUB_KEY" "IBKR_KEY" "APIFY_TOKEN")
for S in "${SECRETS[@]}"; do
    read -rs -p "Enter value for $S: " VAL
    echo -n "$VAL" | gcloud secrets versions add "$S" --data-file=-
    echo -e "\n✅ $S updated."
done

