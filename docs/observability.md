# ## System Observability & Telemetry

### 1. The "Thought Stream" (Logs)
Decisions are logged to Cloud Logging.
* **Filter**: `resource.type="cloud_run_revision" AND resource.labels.service_name="trading-audit-agent"`

### 2. Analytics Tier (BigQuery)
The `performance_logs` table now tracks the "Aberfeldie Constraint":
* **tax_buffer_usd**: Real-time 30% CGT set-aside.
* **daily_hurdle_aud**: The 5.2% opportunity cost of your offset account.
* **net_alpha_usd**: Profitability after tax and mortgage interest.

### 3. Emergency Actuator
Execute the following to flatten all paper positions:
`python3 bot/liquidate.py`

