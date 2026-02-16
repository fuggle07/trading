---

# ## Blueprint: Aberfeldie Agentic Node

**Project:** Nasdaq Concurrent Auditor

**Status:** Multi-Tier Architecture (v2.4 - Python 3.12)

**Deployment Region:** us-central1 (GCP)

**Last Hardened:** 2026-02-16

---

## ### 1. System Architecture

The node is architected as a decoupled, tiered system to ensure that hardware, logic, and security are isolated and modular.

---

## ### 2. The Seven-Step Deployment Sequence

This is the mandatory order of operations for the `setup_node.sh` actuator.

| Step | Tier | Action | Purpose |
| --- | --- | --- | --- |
| **Step -2** | **Security** | `Regenerate Masks` | Generates `.gitignore` & `.gcloudignore` with `#!include`. |
| **Step -1** | **Env** | `Dependency Audit` | Installs `gcloud` & `tfenv/terraform` on Ubuntu. |
| **Step 0** | **Logistics** | `Sync Env` | Pulls `env.yaml` to sync local/cloud variables. |
| **Step 1** | **Infra** | `Terraform Apply` | Provisions GCP Cloud Run, Storage, and IAM roles. |
| **Step 2** | **Identity** | `IAM Hardening` | Applies Least-Privilege roles to the Service Account. |
| **Step 3** | **Secrets** | `Secret Injection` | Moves API keys (Finnhub/IBKR) into Secret Manager. |
| **Step 4** | **Logic** | `Bot Deployment` | Pushes `/bot` code to Cloud Run via `04_deploy_bot.sh`. |

---

## ### 3. Operational Logic & Verification

### #### Component Responsibilities

* **`main.py`:** Orchestrates concurrent audits using `asyncio.gather`.
* **`verification.py`:** Fetches "Hard Proof" (Insider MSPR and SEC Filing Velocity).
* **`liquidate.py`:** Acts as the emergency kill-switch, callable by the bot or manually.
* **`env.yaml`:** Single source of truth for the Nasdaq Watchlist (`BASE_TICKERS`).

### #### Post-Deployment Sanity Check

After initialization, execute the following from the `/scripts` directory:

```bash
./scripts/sanity_test.sh

```

*Expected Result:* A `200 OK` response and concurrent audit logs visible in the GCP Logs Explorer.

---
