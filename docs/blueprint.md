---

## ### Dependency Manifest (`bot/requirements.txt`)

Save this in your `./bot` directory. Note that we have added **BigQuery** support for your performance dashboard.

```text
# GCP & AI Core
# Stable versions for the 2026 Node build
google-cloud-secret-manager==2.26.0
google-cloud-aiplatform==1.77.0
google-cloud-bigquery==3.27.0    # Required for Telemetry Dashboard
functions-framework==3.8.0

# Trading & Exchange Connectivity
# Video: [Mastering ib_async for 2026 Markets](https://www.youtube.com/watch?v=J3VEniAKg5A)
ib_async==2.1.0          # High-performance async IBKR interface
finnhub-python==2.4.19   # Primary MSV Data Source
ccxt==4.1.72             # Unified API for Crypto/Alpaca connectivity

# Data Science & Utilities
pandas==2.2.0
python-dotenv==1.0.1
aiohttp==3.9.3           # For non-blocking concurrent audits

```

---

## ### The "Clean Install" Deployment Sequence

This is the final **7-Step Master Blueprint** for your Aberfeldie Node, ensuring every tier is deployed in the correct logical order.

### #### Step -2 & -1: Provision the Environment

Before touching the cloud, we mask the repository and audit the local Ubuntu system.

```bash
# Executed via the Master setup_node.sh
./scripts/install_dependencies.sh

```

### #### Step 0 & 1: Initialize the "Hardware" (Terraform)

Navigate to the terraform tier to create the BigQuery dataset and Cloud Run shells.
**Video:** [GCP Terraform Quickstart 2026](https://www.youtube.com/watch?v=ypFG006G4WQ)

```bash
cd terraform
terraform init
terraform apply -auto-approve
cd ..

```

### #### Step 2: Harden the "Identity" (IAM)

Enforce **Least Privilege** so the bot can only access the secrets and BigQuery tables it needs.
**Video:** [Securing GCP Service Accounts](https://www.youtube.com/watch?v=r81ISbee2EY)

```bash
./scripts/02_harden_iam.sh

```

### #### Step 3: Inject the "Payload" (Secrets)

Securely move your `FINNHUB_KEY` and `IBKR_KEY` into the Secret Manager.
**Reference:** [Secret Manager CLI Docs](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets)

```bash
./scripts/03_sync_secrets.sh

```

### #### Step 4: Push the "Logic" (Cloud Function)

Package the `./bot` tier. Note that the entry point is now `main_handler` to support concurrent audits.
**Video:** [Deploying Python to Cloud Functions Gen2](https://www.google.com/search?q=https://www.youtube.com/watch%3Fv%3D5aOF-RIZS5c)

```bash
# Executed via ./scripts/04_deploy_bot.sh
gcloud functions deploy trading-audit-agent \
  --gen2 \
  --runtime=python313 \
  --region=us-central1 \
  --source=./bot \
  --entry-point=main_handler \
  --trigger-http \
  --service-account="trading-bot-executor@$(gcloud config get-value project).iam.gserviceaccount.com"

```

---
