---

## ### Dependency Manifest (`requirements.txt`)

Save this in your `./bot` directory. Note that we include `functions-framework`, which is a requirement for GCP Cloud Functions (2nd Gen) to handle HTTP triggers correctly.

```text
# GCP & AI Core
# Stable versions as of Jan 2026
google-cloud-secret-manager==2.26.0
google-cloud-aiplatform==1.77.0
google-cloud-language==2.14.0
functions-framework==3.8.0

# Trading & Exchange Connectivity
# Video: [Mastering ccxt for 2026 Markets](https://www.youtube.com/watch?v=PYW4AIMEvsU)
ib_async==2.1.0          # High-performance async IBKR interface
ccxt==4.1.72             # Unified API for 100+ Crypto exchanges
apify-client==1.7.0      # Stealth scraping for 'Public Noise'

# Data Science & Utilities
pandas==2.2.0
python-dotenv==1.0.1
requests==2.31.0
aiohttp==3.9.3           # For non-blocking async HTTP calls

```

---

## ### The "Clean Install" Deployment Sequence

Now that you have the manifest, here is the final **Master Blueprint** for your physical deployment in Aberfeldie.

### #### Step 1: Initialize the "Hardware" (Terraform)

Run this to create the project shells and the service account.
**Video:** [GCP Terraform Quickstart 2026](https://www.youtube.com/watch?v=ypFG006G4WQ)

```bash
terraform init
terraform apply -auto-approve

```

### #### Step 2: Inject the "Payload" (Secrets)

Use your `sync_secrets.sh` script to securely add your `FINNHUB_KEY` and `IBKR_KEY` to the shells.
**Reference:** [Secret Manager CLI Docs](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets)

```bash
./03_sync_secrets.sh

```

### #### Step 3: Harden the "Identity" (IAM)

Run your `harden_iam.sh` script to enforce **Least Privilege** on the bot.
**Video:** [Securing GCP Service Accounts](https://www.youtube.com/watch?v=r81ISbee2EY)

```bash
./02_harden_iam.sh

```

### #### Step 4: Push the "Logic" (Cloud Function)

This command packages your `./bot` folder (containing `main.py` and your new `requirements.txt`) and pushes it to GCP.
**Video:** [Deploying Python to Cloud Functions Gen2](https://www.google.com/search?q=https://www.youtube.com/watch%3Fv%3D5aOF-RIZS5c)

```bash
gcloud functions deploy trading-audit-agent \
  --gen2 \
  --runtime=python313 \
  --region=us-central1 \
  --source=./bot \
  --entry-point=run_audit \
  --trigger-http \
  --service-account="trading-bot-executor@$(gcloud config get-value project).iam.gserviceaccount.com"

```

---

[Build a Python Trading Bot for Algorithmic Trading Using AI](https://www.youtube.com/watch?v=J3VEniAKg5A)
This tutorial provides a comprehensive walkthrough for building a production-ready trading bot using Python and Interactive Brokers, which is the exact "Actuator" logic needed for your Stage 3 Surgical build.
