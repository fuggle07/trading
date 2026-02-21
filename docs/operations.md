# Operations Manual: Autonomous Trading Bot

**Node ID:** `trading-audit-agent`
**Execution Tier:** GCP Cloud Run
**Deployment Region:** us-central1

---

## 1. Lifecycle Management

### Deployment Command
Deploy infrastructure and bot together using the CI/CD pipeline or manually:

```bash
# Deploy infrastructure (BigQuery tables, Monitoring, Secrets)
cd terraform && terraform apply

# Deploy bot (build Docker image and push to Cloud Run)
./scripts/04_deploy_bot.sh
```

The standard sequence is:
1.  **Build**: `docker buildx build ...`
2.  **Push**: `docker push ...` (Artifact Registry)
3.  **Deploy**: Update Cloud Run service with new image and environment variables.
4.  **Provision**: `terraform apply` to update BigQuery / Monitoring / Secrets.

---

## 2. Secrets Management

The bot relies on the following secrets, stored in **GCP Secret Manager** and injected as environment variables at runtime.

| Secret Name | Provider | Purpose |
| --- | --- | --- |
| `FMP_KEY` | Financial Modeling Prep | Fundamentals, Technicals, Insider Data (primary source) |
| `EXCHANGE_API_KEY` | Finnhub.io | News Sentiment & Macro fallback |
| `ALPACA_API_KEY` | Alpaca | Market Data & Order Execution |
| `ALPACA_API_SECRET` | Alpaca | Market Data & Order Execution |

**Optional / Legacy:**

| Secret Name | Provider | Purpose |
| --- | --- | --- |
| `ALPHA_VANTAGE_KEY` | Alpha Vantage | Supplementary fundamental data (fallback) |
| `MORTGAGE_RATE` | — | Annualised home loan rate (e.g., `0.054`) |
| `INITIAL_CASH` | — | Starting cash pool (default `50000.0`) |
| `BASE_TICKERS` | — | Comma-separated watchlist (default `TSLA,NVDA,MU,AMD,PLTR,COIN,META,MSTR`). **Note**: Hedge tickers (e.g., PSQ) are now auto-injected and do not need to be listed here. |
| `MIN_EXPOSURE_THRESHOLD` | — | Min portfolio exposure before aggression (default `0.65`) |
| `VOLATILITY_SENSITIVITY` | — | Multiplier on the vol threshold (default `1.0`) |

**Sync local secrets to GCP Secret Manager:**
```bash
./scripts/sync_secrets.sh
```

---

## 3. Operational Constraints

### The "Aberfeldie" Constraint
*   **Capital Pool**: **$100,000 USD** (Paper Trading / Simulation mode via Alpaca).
*   **Hurdle Rate**: Set via `MORTGAGE_RATE` env var (e.g., `0.054` = 5.4%).
    *   Tax-adjusted effective hurdle: `Rate × (1 - 0.35)` ≈ **3.5%** annualised.
    *   The bot only deploys capital for opportunities with a high probability of beating this benchmark.

### API Rate Limits
*   **FMP Free Tier**: ~250 requests/day. The bot fetches 3 financial statement endpoints + 3 intelligence metrics + per-ticker technicals per cycle. Monitor usage during heavy cycles.
*   **Finnhub Free Tier**: 60 calls/min. Used primarily for news and macro fallback.
*   **Alpaca**: No practical limit for paper trading data.

---

## 4. Monitoring & Telemetry

### A. Live Log Streaming
```bash
gcloud run services logs tail trading-audit-agent --region us-central1
```

### B. Health Check
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(cd terraform && terraform output -no-color -raw service_url)/health"
```

### C. Live Equity Endpoint
Returns real-time portfolio equity (direct from BigQuery, not cached):
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(cd terraform && terraform output -no-color -raw service_url)/equity"
```
Returns JSON with `total_equity_usd`, `total_cash_usd`, `total_market_value_usd`, `exposure_pct`, and per-position breakdown with unrealized P&L.

### D. Force Audit Trigger
```bash
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(cd terraform && terraform output -no-color -raw service_url)/run-audit"
```

### E. Portfolio State (BigQuery)
```bash
bash scripts/check_portfolio.sh
```

### F. Dashboard
Google Cloud Monitoring: **Aberfeldie Node: NASDAQ Monitor**
- **Paper Equity ($)**: Aggregated with `REDUCE_MAX` across all Cloud Run revisions — shows a single accurate equity line.
- **Capital Allocation**: Cash vs. Assets stacked area — same aggregation fix applied.
- **Portfolio Exposure (%)**: Live exposure percentage.
- **Per-Ticker**: Sentiment, Bollinger Bands, RSI, Conviction, F-Score for each stock.

**Key `performance_logs` Query:**
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
# Alpaca paper: cancel all open orders, close all positions
python3 -c "
from alpaca.trading.client import TradingClient
import os
c = TradingClient(os.environ['ALPACA_API_KEY'], os.environ['ALPACA_API_SECRET'], paper=True)
c.cancel_orders()
c.close_all_positions(cancel_orders=True)
print('All positions closed.')
"
```
*Requires `ALPACA_API_KEY` and `ALPACA_API_SECRET` set in your environment.*

### Force Portfolio Resync
If the BigQuery ledger drifts from Alpaca:
```bash
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(cd terraform && terraform output -no-color -raw service_url)/run-audit"
```
The first phase of every audit cycle is a full reconciliation against Alpaca.

### Service Hard-Stop
```bash
gcloud run services delete trading-audit-agent --region us-central1
```

---

## 6. Known Limitations & Troubleshooting

### FMP API Stability & Restrictions
*   **Symptom**: `FMP [402/403]: ...` or `Legacy Endpoint` errors in logs.
*   **Fix**: The bot has been migrated to modern `/stable/` endpoints. 
*   **VIX Isolation**: ^VIX is fetched independently. If your FMP plan restricts ^VIX, the bot cleanly falls back to **Finnhub** or the **VXX** ETF proxy.

### FMP Free Tier Daily Limit
*   **Symptom**: `FMP [429]` or empty data late in trading day.
*   **Action**: The bot falls back to Finnhub/AlphaVantage for most data. Fundamental health and F-Scores are cached in BigQuery to reduce calls.

### Dashboard Equity Showing Incorrect Value
*   **Cause**: Cloud Monitoring was summing metrics across all Cloud Run revisions.
*   **Fix**: Applied `REDUCE_MAX` with empty `groupByFields` in `monitoring.tf` — deploys via `terraform apply`.
*   **Quick Check**: Hit the `/equity` endpoint directly for source-of-truth equity.

### Reconciler Not Syncing
*   **Symptom**: BigQuery `portfolio` table drifts from Alpaca positions.
*   **Check**: Look for `❌ Portfolio Sync Failed` in logs. Usually caused by missing Alpaca API keys in Secret Manager.
*   **Fix**: Run `./scripts/sync_secrets.sh` then redeploy.
