---

# ## Operations Manual: Aberfeldie Node

**Node ID:** `aberfeldie-01`
**Control Tier:** Ubuntu Workstation (Local)
**Execution Tier:** GCP Cloud Run (Remote)

---

## ### 1. Lifecycle Management

To maintain the node, use the standardized `setup_node.sh` orchestrator. It handles the dependency chain in the correct order:

1. **Scaffold**: `terraform apply -target=google_artifact_registry_repository.repo`
2. **Inject**: `docker buildx build ... && docker push ...`
3. **Realize**: `terraform apply`
4. **Authorize**: `./scripts/03_sync_secrets.sh`

## ### 2. The Health Check Protocol (Authenticated)

Because the service is protected, you must pass a GCloud Identity Token to verify your workstation's authority.

**Standard Connectivity Test:**

```bash
curl -X GET "$(terraform output -no-color -raw service_url)" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"

```

**Force Audit Trigger:**

```bash
curl -X POST "$(terraform output -no-color -raw service_url)/run-audit" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"

```

## ### 3. Telemetry Auditing

The node emits custom metrics to BigQuery every heartbeat.

* **Hurdle Check**: Profit must exceed `daily_hurdle_aud` (5.2% annualized).
* **Tax Check**: `tax_buffer_usd` must be reserved (30% CGT).
* **Net Alpha**: If `net_alpha_usd` stays negative for >7 days, liquidate to offset.

## ### 4. Emergency Procedures

* **Immediate Liquidation**: `python3 bot/liquidate.py`
* **Service Hard-Stop**: `gcloud run services delete trading-audit-agent`

---

### ## BigQuery Verification Query

Run this in the Google Cloud Console to confirm the audit data is landing:

```sql
SELECT 
  timestamp,
  paper_equity,
  daily_hurdle_aud,
  tax_buffer_usd,
  net_alpha_usd,
  recommendation
FROM `utopian-calling-429014-r9.trading_data.performance_logs`
ORDER BY timestamp DESC
LIMIT 5;

```

**Surgical Note:** The use of `$(gcloud auth print-identity-token)` ensures that only your authorized Ubuntu session can trigger the audit engine, protecting your $50,000 USD capital environment from external probes.
