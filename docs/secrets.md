---

# ## Secrets Manifest: Aberfeldie Node

**Project:** Nasdaq Agentic Auditor

**Status:** Multi-Tier Procurement Active

**Last Updated:** 2026-01-27 21:15 AEDT

---

## ### 1. Primary Actuators (Current Build)

These secrets are required for your 7-step deployment sequence.

| Secret Name | Provider | Purpose | Cost (2026) | Obtain From |
| --- | --- | --- | --- | --- |
| `FINNHUB_KEY` | Finnhub.io | SEC Filings & Insider MSV | **Free** (60 calls/min) | [Finnhub Dashboard](https://finnhub.io/dashboard) |
| `ALPACA_KEY` | Alpaca.markets | Dry-Run Execution | **Free** (Unlimited Paper) | [Alpaca Developer Portal](https://alpaca.markets/) |
| `ALPACA_SECRET` | Alpaca.markets | Dry-Run Auth | **Free** | *As above* |
| `IBKR_KEY` | Interactive Brokers | Live Production Actuator | **Free*** (Requires Account) | [IBKR Client Portal](https://www.interactivebrokers.com/) |

> **Surgical Note on IBKR:** While the API is free, IBKR requires a **$500 USD** minimum account balance to maintain active API connectivity.

---

## ### 2. Future Sensors (Scaling Tiers)

As you increase the resolution of your audits, you may want to upgrade to these institutional-grade feeds.

### #### Tier 2: Real-Time & Alternative Data

* **Finnhub Standard ($50 - $130/mo):**
* *Why:* Removes the 60 calls/min bottleneck. Essential if your `BASE_TICKERS` exceeds 50 assets.


* **Apify API Token ($29/mo Starter):**
* *Why:* For "Stealth Scraping" of non-standard sentiment sources (e.g., specific niche forums or X-alternative platforms).


* **Polygon.io ($29 - $200/mo):**
* *Why:* The "Gold Standard" for low-latency Nasdaq tick data. Use this if you move from 5-minute audits to 1-second surgical entries.



### #### Tier 3: The "Black Box" Sensors

* **SEC EDGAR Pro ($45 - $150/mo):**
* *Why:* While our current `verification.py` uses Finnhub, a direct EDGAR Pro subscription provides sub-second alerts on 8-K filings before they hit the aggregators.



---

## ### 3. Estimated Operating Budget (Monthly)

| Phase | Estimated Cost | Components |
| --- | --- | --- |
| **Stage 1 (Dry Run)** | **$0.00** | Free Finnhub + Alpaca Paper + GCP Free Tier* |
| **Stage 2 (Production)** | **$10 - $30** | GCP Compute + IBKR Market Data Fees (Live Snapshots) |
| **Stage 3 (Advanced)** | **$150+** | Finnhub Pro + Apify + Paid SEC Feeds |

**GCP Free Tier covers the first 2 million Cloud Function invocations per month.*

---

## ### 4. 21:15 PM: Security Protocol

* **The Mask:** All secrets listed here must be stored in **GCP Secret Manager** via Step 3 of your `setup_node.sh`.
* **The Leak:** Never place these values in `env.yaml` or `main.py`. If a key is leaked, revoke it immediately at the source (e.g., Finnhub Dashboard) and run `03_sync_secrets.sh` to rotate the value in the cloud.

---

[Interactive Brokers Market Data Fees](https://www.google.com/search?q=https://www.interactivebrokers.com/en/pricing/market-data-fees.php)
This reference is critical for your transition to Stage 2, as it outlines the specific costs for US Equity snapshot data (typically ~$0.01 per request), allowing you to budget for your live Nasdaq actuator.
