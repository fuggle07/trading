# Get URL and Trigger in one go
curl -H "Authorization: bearer $(gcloud auth print-identity-token)" $(gcloud functions describe trading-audit-agent --region=us-central1 --format="value(serviceConfig.uri)")
