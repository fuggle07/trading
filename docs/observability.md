## Repository: System Observability & Telemetry
Project: Aberfeldie Agentic Node

Status: Unified Monitoring Active

Revision: 1.0 (2026-01-27)

### 1. Accessing the Logs (The "Thought Stream")
Your agent writes logs to Cloud Logging. Every decision, rejection, and API call is recorded here.

Direct Link: GCP Logs Explorer

The "Surgical" Query: Copy and paste this into the query builder to see only your bot's high-level decisions:

SQL
resource.type="cloud_run_revision"
resource.labels.service_name="trading-audit-agent"
textPayload:"[DECISION]" OR textPayload:"[MSV AUDIT]"
Execution IDs: In 2026, Cloud Functions automatically group logs by Execution ID. Click on any log entry and select "Show matching entries" to see the entire lifecycle of a specific Nasdaq audit from start to finish.

### 2. Monitoring the Health (The "Heartbeat")
To visualize the performance of your node over time, we use Cloud Monitoring Dashboards.

Direct Link: GCP Dashboards

The Out-of-the-Box View: Look for the "Cloud Run Functions" dashboard. It provides:

Execution Count: How many times your bot triggered.

Latency: How long the AI reasoning took (Gemini 1.5 Pro usually averages 3-5s).

Error Rate: Any 429 (Rate Limit) or 500 (Logic) errors.

### 3. Setting Up "Surgical" Alerts (The "Kill-Switch")
You shouldn't have to watch the logs. Set up Log-Based Alerts to notify you on your phone if something goes wrong.

Step-by-Step Procedure:

Go to Logs Explorer.

Filter for severity >= ERROR.

Click "Create Alert" in the top toolbar.

Name: Aberfeldie-Logic-Failure.

Notification: Select your email or the GCP Mobile App.

### 4. AI Reasoning Analytics (The "Deep Audit")
Since you are using Vertex AI, you can audit the cost and performance of the reasoning engine specifically.

Link: Vertex AI Model Monitoring

Metric to Watch: Token Usage. In env.yaml, if you increase your BASE_TICKERS to 100+, monitor this to ensure your daily AI costs stay within your "Aberfeldie Budget."

### 5. Emergency Actuator (The "Liquidator")
If you see an anomaly in the logs (e.g., the bot is entering trades it shouldn't), execute your emergency script from your terminal:

Bash
# Emergency Actuator: Closes all open positions and halts the bot
python3 bot/liquidate.py

