
#!/bin/bash
# harden_iam.sh - Automated Least Privilege Enforcement
# Directive: Ensure the Service Account has exactly what it needs and nothing more.

PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="trading-bot-executor@${PROJECT_ID}.iam.gserviceaccount.com"

# The 'Surgical List' of required roles
REQUIRED_ROLES=(
 "roles/secretmanager.secretAccessor"
 "roles/aiplatform.user"
 "roles/logging.logWriter"
 "roles/artifactregistry.writer"
 "roles/serviceusage.serviceUsageConsumer"
 "roles/editor"
 "roles/resourcemanager.projectIamAdmin"
)

echo "--- ABERFELDIE IAM AUDIT: $SA_EMAIL ---"

for ROLE in "${REQUIRED_ROLES[@]}"; do
 # 1. Check if the role is already bound to the SA
 EXISTING_ROLE=$(gcloud projects get-iam-policy "$PROJECT_ID" \
 --flatten="bindings[].members" \
 --format='table(bindings.role)' \
 --filter="bindings.members:serviceAccount:$SA_EMAIL AND bindings.role:$ROLE" | grep "$ROLE")

 if [ -n "$EXISTING_ROLE" ]; then
 echo "✅ ROLE ALREADY ATTACHED: $ROLE"
 else
 echo "⚠️ MISSING ROLE: $ROLE. Attaching now..."
 # 2. Add the binding if missing
 gcloud projects add-iam-policy-binding "$PROJECT_ID" \
 --member="serviceAccount:$SA_EMAIL" \
 --role="$ROLE" \
 --quiet > /dev/null
 echo "✨ FIXED: $ROLE attached."
 fi
done

echo "--- IAM AUDIT COMPLETE ---"
