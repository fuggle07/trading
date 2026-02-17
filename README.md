# # Aberfeldie Trading Node: Nasdaq Concurrent Auditor

An autonomous, agentic trading node deployed on Google Cloud Platform, designed to manage **$50,000 USD** of capital while auditing performance against a **5.2% mortgage offset hurdle**.

---

## ## Project Overview
The Aberfeldie Node is a high-frequency audit agent that monitors Nasdaq market opportunities. Its primary function is to determine if capital is more effectively deployed in live markets or returned to a high-interest Australian offset account.

### ### Core Logic
* **Concurrent Market Sensing**: Real-time AUD/USD forex polling via Frankfurter API.
* **Hurdle Telemetry**: Real-time calculation of opportunity cost (5.2% home loan interest).
* **Tax Guardrails**: Automated 30% CGT buffer calculation for Australian tax compliance.
* **Agentic Execution**: Flask-based logic engine running on Cloud Run v2.

---

## ## Tech Stack
* **Language**: Python 3.11 (Flask, Gunicorn, Asyncio)
* **Infrastructure**: Terraform (IaC)
* **Containerization**: Docker Buildx (BuildKit)
* **Data Silo**: BigQuery (Performance Logs)
* **Secret Tier**: GCP Secret Manager (IBKR & Finnhub keys)

---

## ## Quick Start (Deployment)
From your Ubuntu workstation, execute the master orchestrator:

```bash
chmod +x setup_node.sh
./setup_node.sh
