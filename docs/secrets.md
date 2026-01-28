# ## Secrets Manifest: Aberfeldie Node

**Project:** Nasdaq Agentic Auditor
**Status:** Production Tier (IBKR Live)
**Last Updated:** 2026-01-28 13:00 AEDT

---

## ### 1. Production Actuators (Current Build)

These secrets are surgically mapped to your Cloud Run environment variables for live Nasdaq audits.

| Secret Name | Provider | Purpose | Format |
| --- | --- | --- | --- |
| `FINNHUB_KEY` | Finnhub.io | SEC Filing & Insider Sensors | `string` |
| `IBKR_KEY` | IBKR | Live Trade Actuator | `username:password` |
| `APIFY_TOKEN` | Apify.com | Alternative Sentiment Scraper | `string` |

---

## ### 2. The "Aberfeldie" Constraint (Telemetry)

While not stored as secrets, these constants drive the audit engine's logic in `main.py`.

* **Home Loan Hurdle:** 5.2% (Calculated daily against $50k USD capital).
* **Tax Buffer:** 30% CGT reserve for Australian taxable events.
* **FX Sensor:** Frankfurter API (Concurrent AUD/USD polling).

---

## ### 3. Security & Sync Protocol

To prevent leaks of your $50,000 USD capital environment, follow the **Zero-File-Persistence** rule:

1. **Initial Provisioning:** Terraform creates the secret containers with `PLACEHOLDER_INIT` values to allow Cloud Run to deploy without crashing.
2. **Live Injection:** Run `scripts/03_sync_secrets.sh` to securely push your real keys from your local workstation into GCP Secret Manager.
3. **Mounting:** Cloud Run mounts these as environment variables at runtime. They are never written to disk or logged.

---

## ### 4. Operating Costs (Monthly Estimate)

| Tier | Estimated Cost | Components |
| --- | --- | --- |
| **GCP Compute** | **$0 - $10** | Cloud Run (Tier 1) + Secret Manager |
| **Market Data** | **$10 - $20** | IBKR US Equity Snapshots (~$0.01/snapshot) |
| **Total Hurdle** | **$220+** | Monthly interest cost of $50k loan @ 5.2% |

> **Surgical Note:** The bot must generate >$220 USD/month in profit just to break even against your offset account interest.

