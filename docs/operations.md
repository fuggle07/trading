# Operations Manual: Autonomous Trading Bot

**Node ID:** `trading-audit-agent`
**Execution Tier:** GCP Cloud Run
**Deployment Region:** us-central1

---

## 1. Lifecycle Management

To maintain the node, use the standardized `setup_node.sh` orchestrator. It handles the dependency chain in the correct order:

1.  **Build**: `docker buildx build ...`
2.  **Push**: `docker push ...` (to Artifact Registry)
3.  **Deploy**: Updates Cloud Run service with new image and environment variables.
4.  **Provision**: Applies Terraform configuration for BigQuery and Secret Manager.

### Deployment Command
```bash
./setup_node.sh
```

---

## 2. Secrets Management

The bot relies on the following secrets, stored securely in **GCP Secret Manager** and injected as environment variables at runtime.

| Secret Name | Provider | Purpose |
| --- | --- | --- |
| `FINNHUB_KEY` | Finnhub.io | News Sentiment & Filing Data |
| `ALPACA_API_KEY` | Alpaca | Market Data & Order Execution |
| `ALPACA_API_KEY` | Alpaca | Market Data & Order Execution |
| `ALPACA_API_SECRET` | Alpaca | Market Data & Order Execution |
| `ALPHA_VANTAGE_KEY` | Alpha Vantage | Fundamental Data (PE/EPS) |

**Sync Protocol**:
To update or inject new keys, ensure they are in your local `.env` file (or exported in your shell) and run:
```bash
# Example:
export ALPACA_API_KEY="your_key"
export ALPACA_API_KEY="your_key"
export ALPACA_API_SECRET="your_secret"
export ALPHA_VANTAGE_KEY="your_key"
./setup_node.sh
```
*Note: `setup_node.sh` has logic to sync local variables to Secret Manager.*

---

## 3. Operational Costs & Hurdles

### The "Aberfeldie" Constraint
The system operates under strict financial performance hurdles:

*   **Capital Pool**: **$100,000 USD** (Paper Trading / Simulation).
*   **Hurdle Rate**: **6.0%** Annualized (Home Loan Offset Benchmark).
    *   The bot must outperform this rate to justify its deployed capital.
*   **Tax Buffer**: **35%** of realized gains are conceptually set aside for CGT.

---

## 4. Monitoring & Telemetry

### A. Health Checks & Live Monitoring
**Stream Live Logs (Best for Trading Hours):**
```bash
./scripts/live_logs.sh
```
*Tip: Keeps a real-time connection to the Cloud Run service output.*

**Standard Connectivity Test:**
```bash
curl -X GET "$(terraform output -no-color -raw service_url)" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

**Force Audit Trigger:**
```bash
./scripts/trigger_bot.sh
```

### B. BigQuery Analytics
All operational data is streamed to the `trading_data` dataset.

**Key Tables**:
*   `portfolio`: Real-time state of Cash and Holdings.
*   `executions`: History of all filled orders.
*   `performance_logs`: Snapshot of Total Equity over time.
*   `watchlist_logs`: Detailed decision log (Signal, Sentiment, Volatility).

**Verification Query (Performance):**
```sql
SELECT timestamp, paper_equity, node_id
FROM `utopian-calling-429014-r9.trading_data.performance_logs`
ORDER BY timestamp DESC
LIMIT 5;
```

---

## 5. Emergency Procedures

### Immediate Liquidation
To flatten all positions immediately (move to 100% Cash):
```bash
python3 bot/liquidate.py
```
*Note: This script requires `ALPACA_API_KEY` and `ALPACA_API_SECRET` to be set in your local environment.*

### Service Hard-Stop
To delete the Cloud Run service and stop all execution:
```bash
gcloud run services delete trading-audit-agent --region us-central1
```

---

## 6. Known Limitations & Troubleshooting

### Finnhub Free Tier Constraints
*   **Restriction**: The free tier has strict rate limits and restricted access to historical data.
*   **Symptom**: You may see `403 Forbidden` errors in the logs for "Historical Data".
*   **Handling**: The bot gracefully handles this by logging the price and skipping the trade strategy for that cycle. Data from Alpaca is used for the primary decision making, so this is non-critical.
