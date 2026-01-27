## Repository: Agentic Trading Node References
Project: Aberfeldie Post-Pivot Build

Revision: 1.0 (2026-01-27)

Status: High-Fidelity Infrastructure

### 1. Infrastructure & Deployment (GCP/Terraform)
These resources cover the "Hardened Shell" of your system. They ensure your environment is reproducible, secure, and cost-optimized.

GCP Terraform Basics * Context: Essential for understanding the logic behind the main.tf file we generated.

Secret Manager Product Guide * Context: Critical for securing your IBKR and Binance API keys away from your source code.

Cloud Functions 2nd Gen Deployment * Context: How to deploy the "Event-Driven" agent that wakes up every 5 minutes.

Cloud Function Debug & Deploy with VS Code * Context: Managing your Python lifecycle from your local development environment.

### 2. The Reasoning Engine (Vertex AI)
These links focus on the "Brain" of the operation—how to use Gemini 1.5 Pro to perform surgical audits of market data.

Vertex AI Setup Guide * Context: Configuring the permissions needed for your agent to access LLMs.

Build a Financial Analyst Assistant with Vertex AI * Context: The core blueprint for an agent that performs sentiment and technical analysis.

### 3. Exchange Connectivity (The "Actuators")
Specific technical deep-dives into connecting your Python code to real-world markets.

Interactive Brokers API with ib_async * Context: Using modern, asynchronous Python to talk to IBKR without latency.

Interactive Brokers API Tutorial (General) * Context: Foundational knowledge on how the IBKR TWS gateway operates.

Binance Python Trading Bot Guide * Context: Direct implementation of crypto exchange hooks.

Simplest Binance Bot Tutorial (CCXT) * Context: Using the CCXT library for a "Universal" exchange interface.

Binance Testnet Tutorial * Context: Essential for the "Paper Trading" phase before committing capital.

### 4. Data Visualization (The Post-Mortem)
Tools to audit your agent's performance and ensure your "Logic" is actually outperforming the index.

Connecting BigQuery to Looker Studio * Context: How to turn your BigQuery logs into the "Surgical Dashboard" we designed.

### 5. General Context & Strategy
Getting started with Algorithmic Trading * Context: A high-level overview of market structures for quants.

