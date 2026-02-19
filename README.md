# Aberfeldie Trading Bot 🚀

High-frequency algorithmic trading system with an AI-driven fundamental analysis engine and automated portfolio management.

## 📂 Project Structure

### `/bot`
The core engine of the trading bot.
- `main.py`: Entry point for the trading logic and audit cycles.
- `fundamental_agent.py`: Advanced fundamental analysis (DCF, F-Score, Quality Score).
- `signal_agent.py`: Strategy evaluation and execution signals.
- `execution_manager.py`: Handles interaction with Alpaca markets.
- `portfolio_manager.py`: Manages local position and equity tracking.
- `ticker_ranker.py`: Morning analysis tasks and ranking logic.
- `feedback_agent.py`: Intraday AI feedback loop (logs analysis).

### `/utilities`
Standalone tools for manual auditing, diagnosis, and system maintenance.
- `live_logs.sh`: Live log streaming from Cloud Run.
- `rank_tickers.py`: Manual trigger for morning ranking.
- `check_portfolio_health.py`: Full fundamental audit of current holdings.
- `liquidate.py`: **Emergency Stop** - Closes all positions and resets ledger.
- `diagnose_feed.py`: Verify exchange data API health.

### `/scripts`
Deployment, infrastructure, and automation scripts.
- `01_deploy_infra.sh`: Terraform infrastructure deployment.
- `04_deploy_bot.sh`: Build and deploy the Docker image to Cloud Run.
- `05_sync_env.sh`: Sync local `.env` with GitHub secrets and Cloud Run.

### `/terraform`
IaC (Infrastructure as Code) definitions for Google Cloud resources.
- BigQuery datasets/tables.
- Cloud Run service configuration.
- Monitoring dashboards and log-based alerts.

## 🛠️ Usage

### Streaming Logs
```bash
./utilities/live_logs.sh
```

### Auditing Portfolio Health
```bash
python3 utilities/check_portfolio_health.py
```

### Manual Ranking
```bash
python3 utilities/rank_tickers.py
```

---
*Note: Ensure your `PROJECT_ID` and API keys are set in the `.env` file or environment.*
