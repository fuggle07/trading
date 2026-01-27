# main.tf - Unified Aberfeldie Node Infrastructure
provider "google" {
  project = var.project_id
  region  = "us-central1"
}

# 1. CORE COMPUTE & STORAGE SHELLS
resource "google_artifact_registry_repository" "repo" {
  location      = "us-central1"
  repository_id = "trading-node-repo"
  format        = "DOCKER"
}

resource "google_service_account" "bot_sa" {
  account_id   = "trading-bot-executor"
  display_name = "Trading Bot Service Account"
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["FINNHUB_KEY", "IBKR_KEY", "APIFY_TOKEN"])
  secret_id = each.key
  replication {
    user_managed {
      # For a simpler 'auto' setup in 2026:
      # If your provider version supports it, use:
    }
    # Standard 'automatic' replication for global nodes:
    automatic = true 
  }
}

# 2. CLOUD RUN SERVICE (The missing resource for your scheduler)
resource "google_cloud_run_v2_service" "trading_bot" {
  name     = "trading-audit-agent"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.bot_sa.email
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/trading-node-repo/trading-bot:latest"
      
      # Injecting Secrets as Env Vars
      env {
        name = "FINNHUB_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secrets["FINNHUB_KEY"].secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# 3. UNIFIED ANALYTICS TIER (BigQuery)
resource "google_bigquery_dataset" "trading_data" {
  dataset_id                 = "trading_data"
  friendly_name              = "Aberfeldie Trading Analytics"
  description                = "Unified performance, tax, and hurdle logs"
  location                   = "us-central1"
  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "performance_logs" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "performance_logs"
  deletion_protection = true # Critical for historical tax data

  schema = <<EOF
[
  {
    "name": "timestamp",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "UTC Execution Time"
  },
  {
    "name": "paper_equity",
    "type": "FLOAT",
    "mode": "REQUIRED",
    "description": "Total account value (USD)"
  },
  {
    "name": "index_price",
    "type": "FLOAT",
    "mode": "REQUIRED",
    "description": "Benchmark price (e.g., QQQ)"
  },
  {
    "name": "fx_rate_aud",
    "type": "FLOAT",
    "mode": "REQUIRED",
    "description": "USD to AUD rate for ATO reporting"
  },
  {
    "name": "brokerage_fees_usd",
    "type": "FLOAT",
    "mode": "NULLABLE",
    "description": "Deductible transaction costs"
  },
  {
    "name": "opportunity_cost_aud",
    "type": "FLOAT",
    "mode": "NULLABLE",
    "description": "Daily interest saved if capital stayed in 5.2% offset"
  },
  {
    "name": "node_id",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "Source Node Identifier"
  }
]
EOF
}

# 4. MONITORING TIER
resource "google_monitoring_notification_channel" "email" {
  display_name = "Trading Alerts"
  type         = "email"
  labels = {
    email_address = "your-email@example.com"
  }
}

resource "google_monitoring_alert_policy" "logic_failure_alert" {
  display_name = "Logic Failure Alert"
  combiner     = "OR"
  conditions {
    display_name = "Error log detected"
    condition_matched_log {
      filter = "resource.type=\"cloud_run_revision\" textPayload:\"ERROR\""
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.name]
}
