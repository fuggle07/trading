# Antigravity Development Rules - Trading Bot & Cloud Platform

## 1. Architectural Principles
- **IaC Sovereignty:** All infrastructure must be defined in Terraform. Do not generate scripts that create cloud resources via SDKs; use SDKs only for data plane operations.
- **Stateless Logic:** Decouple data ingestion (BigQuery/APIs), signal generation (indicators), and execution (order placement).
- **Idempotency:** All scripts must be safe to re-run. Check for existing resources or states before execution.

## 2. Python Coding Standards
- **Financial Precision:** STICK TO THE `decimal` MODULE. Never use `float` for currency, coin quantities, or price calculations to avoid floating-point errors.
- **Type Safety:** Use Python type hints for all function arguments and return types.
- **Async Strategy:** Use `asyncio` and `aiohttp` for exchange API interactions to minimize latency.
- **Error Handling:** Implement explicit try-except blocks for `RequestException` and `json.JSONDecodeError`. Use exponential backoff for rate-limited endpoints.

## 3. Risk Management & Safety (CRITICAL)
- **Slippage Guard:** Every order execution function must include a `max_slippage` parameter, defaulting to 0.005 (0.5%).
- **Kill Switch:** Maintain a global `trading_enabled` flag (via GCP Secret Manager or Environment Variable). If `False`, all order functions must return a "Safety Bypass" status.
- **Position Sizing:** All trade sizes must be calculated as a percentage of available equity, never a hard-coded constant.

## 4. Terraform & GCP Standards
- **Secrets Management:** Reference GCP Secret Manager for all API keys and credentials. Never commit plaintext secrets or use `.env` files.
- **State Management:** Use a GCS remote backend for Terraform state.
- **Naming & Tagging:** Apply standard tags: `Project: trading-bot`, `Owner: p-fuggle`, `Environment: prod`.

## 5. Logging & Observability
- **BigQuery Integration:** Every signal (win or loss) must be logged to the `trading_logs` dataset with a timestamp, raw signal data, and executed price.
- **Structured Logs:** Use `google-cloud-logging` to output JSON-formatted logs for easy filtering in the GCP Console.
