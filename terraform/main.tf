# main.tf - Unified Aberfeldie Node Blueprint (v3.4)
provider "google" {
  project = var.project_id
  region  = "us-central1"
}

variable "project_id" {
  type        = string
  description = "The GCP Project ID"
}
variable "mortgage_rate" {
  description = "The annual mortgage interest rate (e.g., 0.06 for 6%)"
  type        = number
  default     = 0.0514 # NAB actual 20260129
}

# 1. SECRET MANAGEMENT TIER
# Fixed: Expanded nested blocks for HCL compliance
resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["FINNHUB_KEY", "IBKR_KEY", "APIFY_TOKEN"])
  secret_id = each.key

  replication {
    auto {} # This replaces "automatic = true"
  }
}

# 2. ANALYTICS TIER (BigQuery)
resource "google_bigquery_dataset" "trading_data" {
  dataset_id                 = "trading_data"
  friendly_name              = "Aberfeldie Trading Analytics"
  location                   = "us-central1"
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "performance_logs" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "performance_logs"
  deletion_protection = false # Keeping this false while we iterate on the schema

  schema = <<EOF
[
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "paper_equity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "tax_buffer_usd", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "fx_rate_aud", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "daily_hurdle_aud", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "net_alpha_usd", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "node_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "recommendation", "type": "STRING", "mode": "NULLABLE"},
  { "name": "sentiment_score", "type": "FLOAT", "mode": "NULLABLE" },
  { "name": "social_volume", "type": "INTEGER", "mode": "NULLABLE" }
]
EOF
}

resource "google_bigquery_table" "watchlist_logs" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  table_id   = "watchlist_logs"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker", "type": "STRING", "mode": "REQUIRED" },
  { "name": "price", "type": "FLOAT", "mode": "REQUIRED" },
  { "name": "sentiment_score", "type": "FLOAT", "mode": "NULLABLE" }
]
EOF
}

# 3. COMPUTE TIER (Artifact Registry & Cloud Run)
resource "google_artifact_registry_repository" "repo" {
  location      = "us-central1"
  repository_id = "trading-node-repo"
  format        = "DOCKER"
}

resource "google_service_account" "bot_sa" {
  account_id   = "trading-bot-executor"
  display_name = "Trading Bot Service Account"
}

resource "google_cloud_run_v2_service" "trading_bot" {
  name     = "trading-audit-agent"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  depends_on = [google_secret_manager_secret_version.initial_versions]

  template {
    # 1. KEEP THE BOT ALIVE 24/7
    scaling {
      min_instance_count = 1
      max_instance_count = 3
    }
    service_account = google_service_account.bot_sa.email
    containers {
      # Liveness probe: Checks if the app is still alive
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }

      # Startup probe: Gives the app time to boot up
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 5
      }
      image = "us-central1-docker.pkg.dev/${var.project_id}/trading-node-repo/trading-bot:latest"
      
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      # Inject the rate here
      env {
        name  = "MORTGAGE_RATE"
        value = tostring(var.mortgage_rate)
      }
      env {
        name = "EXCHANGE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "FINNHUB_KEY" # Mapping your Finnhub key to the bot's generic var
            version = "latest"
          }
        }
      }
      env {
        name  = "TRADING_ENABLED"
        value = "True" # Or use a variable
      }
      env {
        name  = "BASE_TICKERS"
        value = "NVDA,AAPL,TSLA,MSFT,AMD"
      }
      env {
        name  = "DEPLOY_TIME"
        value = var.deploy_time
      }
    }
  }
}

# 3. SECRET ACCESS (Re-confirming for completeness)
resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each  = toset(["FINNHUB_KEY", "IBKR_KEY", "APIFY_TOKEN"])
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.bot_sa.email}"
}

# CREATE INITIAL SECRET VERSIONS
# This ensures the 'latest' alias exists for Cloud Run
resource "google_secret_manager_secret_version" "initial_versions" {
  for_each    = google_secret_manager_secret.secrets
  secret      = each.value.id
  secret_data = "PLACEHOLDER_INIT" # To be overwritten by 03_sync_secrets.sh

  # Ensure permissions are granted before Cloud Run tries to read them
  depends_on = [google_secret_manager_secret_iam_member.secret_access]
}
# EXPOSE THE SERVICE URL FOR SCRIPTS
output "service_url" {
  value       = google_cloud_run_v2_service.trading_bot.uri
  description = "The public URL of the Aberfeldie Trading Node"
}

# 1. Create the Portfolio Table
resource "google_bigquery_table" "portfolio" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  table_id   = "portfolio"
  deletion_protection = false # Set to true for production high-res safety

  schema = <<EOF
[
  {
    "name": "asset_name",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "holdings",
    "type": "FLOAT",
    "mode": "REQUIRED"
  },
  {
    "name": "avg_price",
    "type": "FLOAT",
    "mode": "NULLABLE",
    "description": "Weighted Average Cost Basis for Stop Loss calculation"
  },
  {
    "name": "cash_balance",
    "type": "FLOAT",
    "mode": "REQUIRED"
  },
  {
    "name": "last_updated",
    "type": "TIMESTAMP",
    "mode": "REQUIRED"
  }
]
EOF
}

resource "google_bigquery_table" "executions" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  table_id   = "executions"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "execution_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "ticker", "type": "STRING", "mode": "REQUIRED"},
  {"name": "action", "type": "STRING", "mode": "REQUIRED"},
  {"name": "quantity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "price", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "reason", "type": "STRING", "mode": "NULLABLE"},
  {"name": "status", "type": "STRING", "mode": "REQUIRED"}
]
EOF
}

# 2. Harden IAM for the Bot
# The bot now needs to run Queries (Job User) and Update data (Data Editor)
resource "google_project_iam_member" "bot_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

# BQ Data Editor: Permission to write to tables
resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

# BQ Job User: Permission to start an 'insert' job (Required)
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

resource "google_bigquery_dataset_iam_member" "bot_bq_editor" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.bot_sa.email}"
}

# Create a dedicated high-retention bucket for the system audit

# Update the Dataset for Log Analytics
resource "google_bigquery_dataset" "system_logs" {
  dataset_id                  = "system_logs"
  location                    = "us-central1" 
  description                 = "Aggregated master logs for the trading node"
  delete_contents_on_destroy = false
}

# Update the Logging Bucket
resource "google_logging_project_bucket_config" "audit_log_bucket" {
    project        = var.project_id
    location       = "us-central1"
    retention_days = 365 
    bucket_id      = "system-audit-trail"
}

# Create the Master Log Sink
resource "google_logging_project_sink" "master_log_sink" {
  name        = "trading-system-master-sink"
  description = "Routes structured audit logs from all Cloud Run services to BigQuery"
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.system_logs.dataset_id}"

  # Filter to only capture your high-resolution structured logs
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.component:\"*\""

  unique_writer_identity = true
}

# Grant the Sink permission to write to BigQuery
resource "google_project_iam_member" "log_sink_writer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = google_logging_project_sink.master_log_sink.writer_identity
}

# 4. SCHEDULING TIER (NASDAQ Aligned)
resource "google_cloud_scheduler_job" "nasdaq_trigger" {
  name             = "trading-trigger-nasdaq"
  description      = "Aligned to NASDAQ hours (New York time) - DST Proof"

  # Runs every 5 mins from 9:00 AM to 4:00 PM, Monday-Friday (NY Time)
  schedule         = "*/5 9-16 * * 1-5"

  # This is the "Magic" that handles DST drift for you
  time_zone        = "America/New_York"

  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.trading_bot.uri}/run-audit"

    oidc_token {
      service_account_email = google_service_account.bot_sa.email
    }
  }
}

# C. Log-Based Metrics (To bridge Logs -> Dashboard)
# C. Log-Based Metrics (To bridge Logs -> Dashboard)
resource "google_logging_metric" "paper_equity" {
  name   = "trading/paper_equity"
  # Updated filter to match the actual log message: "📈 Logged Performance: $..."
  # AND ensures the payload has the 'paper_equity' key we need.
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key         = "node_id"
      value_type  = "STRING"
      description = "The Bot ID"
    }
  }
  label_extractors = {
    "node_id" = "EXTRACT(jsonPayload.node_id)"
  }
  value_extractor = "EXTRACT(jsonPayload.paper_equity)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "sentiment_score" {
  name   = "trading/sentiment_score"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged .* Sentiment\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = {
    "ticker" = "EXTRACT(jsonPayload.ticker)"
  }
  value_extractor = "EXTRACT(jsonPayload.sentiment_score)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 0.1
      offset             = -1.0
    }
  }
}

resource "google_monitoring_dashboard" "nasdaq_bot_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Aberfeldie Node: NASDAQ Monitor"
    mosaicLayout = {
      columns = 12
      tiles = [
        # WIDGET 1: Cloud Run Success/Failure Rate
        {
          width = 6, height = 4, xPos = 0, yPos = 0
          widget = {
            title = "Cloud Run: Request Status (2xx vs 4xx/5xx)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"trading-audit-agent\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields = ["metric.label.response_code_class"]
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 2: Execution Latency
        {
          width = 6, height = 4, xPos = 6, yPos = 0
          widget = {
            title = "Cloud Run: Latency (ms)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"trading-audit-agent\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_99"
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 3: Total Equity
        {
          width = 6, height = 4, xPos = 0, yPos = 4
          widget = {
            title = "💰 Paper Equity ($)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/trading/paper_equity\""
                    aggregation = {
                      alignmentPeriod = "300s"
                      perSeriesAligner = "ALIGN_PERCENTILE_50"
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 4: Sentiment Heatmap
        {
          width = 6, height = 4, xPos = 6, yPos = 4
          widget = {
            title = "📰 Market Sentiment (-1 to +1)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\""
                    aggregation = {
                      alignmentPeriod = "300s"
                      perSeriesAligner = "ALIGN_PERCENTILE_50"
                      groupByFields = ["metric.label.ticker"]
                    }
                  }
                }
              }]
            }
          }
        }
      ]
    }
  })
}
# A. Notification Channel (Where the alert goes)
resource "google_monitoring_notification_channel" "email_me" {
  display_name = "Trading Bot Alerts"
  type         = "email"
  labels = {
    email_address = "pfuggle@gmail.com"
  }
}

# B. Bot Failure Alert (Instead of Dead Man's Switch)
resource "google_monitoring_alert_policy" "bot_failure" {
  display_name = "CRITICAL: Aberfeldie Node Failure (5xx Errors)"
  combiner     = "OR"
  notification_channels = [google_monitoring_notification_channel.email_me.name]

  conditions {
    display_name = "Cloud Run 5xx Errors"
    condition_threshold {
      filter     = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"trading-audit-agent\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.label.response_code_class = \"5xx\""
      duration   = "60s"
      comparison = "COMPARISON_GT"
      threshold_value = 0
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  documentation {
    content = "The trading bot is returning 5xx errors. Check Cloud Run logs immediately for crashes or exceptions."
  }
}
output "dashboard_url" {
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${element(split("/", google_monitoring_dashboard.nasdaq_bot_dashboard.id), 3)}?project=${var.project_id}"
  description = "The direct link to the NASDAQ Monitor Dashboard"
}
