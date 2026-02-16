# ## Blueprint: Aberfeldie Agentic Node (v3.0)

**Project:** Nasdaq Concurrent Auditor
**Status:** Containerized Multi-Tier Architecture
**Last Hardened:** 2026-01-28

---

## ### 1. System Architecture
The node is architected as a decoupled system using **Cloud Run** for compute and **BigQuery** for hurdle-aware telemetry.

## ### 2. The Master Deployment Sequence

| Step | Tier | Action | Purpose |
| --- | --- | --- | --- |
| **Step 0** | **Identity** | `Auth Check` | Verifies gcloud and docker-buildx permissions. |
| **Step 1** | **Infra A** | `Terraform Target` | Provisions Artifact Registry and BigQuery Dataset. |
| **Step 2** | **Software** | `Build & Push` | Builds Docker image and pushes to Registry. |
| **Step 3** | **Infra B** | `Terraform Apply` | Finalizes Cloud Run and Secret Manager versions. |
| **Step 4** | **Sync** | `Secret Injection` | Moves live keys into Secret Manager. |

## ### 3. Dependency Manifest (`bot/requirements.txt`)
Updated for 2026 performance standards (Python 3.12):
* **google-cloud-bigquery**: Telemetry streaming (fixed for Py3.12).
* **ib_async**: High-performance IBKR interface.
* **httpx**: Async forex polling & integration testing.
* **gunicorn**: Production WSGI server for Cloud Run.
* **pytest / flake8**: Development quality assurance.


