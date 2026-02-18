# Aberfeldie Trading Node: Nasdaq Concurrent Auditor

An autonomous, agentic trading node deployed on Google Cloud Platform, designed to manage **$100,000 USD** of capital while auditing performance against a **6.0% mortgage offset hurdle**.

---

## Project Overview
The Aberfeldie Node is a high-frequency audit agent that monitors Nasdaq market opportunities. Its primary function is to determine if capital is more effectively deployed in live markets or returned to a high-interest Australian offset account.

### Core Logic
* **Intelligence Gathering**: Parallel polling of indicators, sentiment, and fundamental health.
* **Hurdle Telemetry**: Real-time calculation of opportunity cost (6.0% home loan interest).
* **AI Conviction**: Deep news analysis via Gemini 2.0 Flash with score/confidence filtering.
* **Portfolio Rebalancing**: Coordinated "Conviction Swaps" to rotate capital among laggards and stars.
* **Tax Guardrails**: Automated 35% CGT buffer calculation for Australian tax compliance.
* **Agentic Execution**: Flask-based logic engine running on Cloud Run v2 with Alpaca Paper Trading.

---

## Tech Stack
* **Language**: Python 3.12 (Flask, Gunicorn, Asyncio)
* **AI**: Vertex AI (Gemini 2.0 Flash)
* **Infrastructure**: Terraform (IaC)
* **Data Silo**: BigQuery (Execution, Portfolio, Cache, & Performance Logs)
* **Secret Tier**: GCP Secret Manager (Alpaca, Finnhub, & Alpha Vantage keys)

---

## Quick Start (Deployment)
From your workstation, execute the master orchestrator:

```bash
chmod +x setup_node.sh
./setup_node.sh
```
