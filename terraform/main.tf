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
  for_each  = toset(["FINNHUB_KEY", "IBKR_KEY", "APIFY_TOKEN", "ALPACA_API_KEY", "ALPACA_API_SECRET", "ALPHA_VANTAGE_KEY"])
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
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "watchlist_logs"
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

# Enable Vertex AI API for Gemini
resource "google_project_service" "aiplatform" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

# Enable Billing Budgets API
resource "google_project_service" "billing_budgets" {
  project            = var.project_id
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
}

resource "google_cloud_run_v2_service" "trading_bot" {
  name                = "trading-audit-agent"
  location            = "us-central1"
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  depends_on          = [google_secret_manager_secret_version.initial_versions]

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
        name = "ALPACA_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "ALPACA_API_KEY"
            version = "latest"
          }
        }
      }
      env {
        name = "ALPACA_API_SECRET"
        value_source {
          secret_key_ref {
            secret  = "ALPACA_API_SECRET"
            version = "latest"
          }
        }
      }
      env {
        name = "ALPHA_VANTAGE_KEY"
        value_source {
          secret_key_ref {
            secret  = "ALPHA_VANTAGE_KEY"
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
        value = "NVDA,AAPL,TSLA,MSFT,AMD,PLTR,COIN"
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
  for_each   = toset(["FINNHUB_KEY", "IBKR_KEY", "APIFY_TOKEN", "ALPACA_API_KEY", "ALPACA_API_SECRET", "ALPHA_VANTAGE_KEY"])
  secret_id  = each.key
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.bot_sa.email}"
  depends_on = [google_secret_manager_secret.secrets]
}

# 4. CLOUD RUN INVOKER (For Scheduler)
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.trading_bot.location
  name     = google_cloud_run_v2_service.trading_bot.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.bot_sa.email}"
}

# 5. SCHEDULER ACCESS (Allow Scheduler to impersonate the bot SA for OIDC)
# Note: Using project number derived from the environment or a data source is preferred
data "google_project" "project" {}

resource "google_service_account_iam_member" "scheduler_sa_user" {
  service_account_id = google_service_account.bot_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
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
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "portfolio"
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
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "executions"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "execution_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "alpaca_order_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "ticker", "type": "STRING", "mode": "REQUIRED"},
  {"name": "action", "type": "STRING", "mode": "REQUIRED"},
  {"name": "quantity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "price", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "commission", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "reason", "type": "STRING", "mode": "NULLABLE"},
  {"name": "status", "type": "STRING", "mode": "REQUIRED"}
]
EOF
}

resource "google_bigquery_table" "ticker_rankings" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "ticker_rankings"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker", "type": "STRING", "mode": "REQUIRED" },
  { "name": "sentiment", "type": "FLOAT", "mode": "REQUIRED" },
  { "name": "confidence", "type": "INTEGER", "mode": "REQUIRED" },
  { "name": "reason", "type": "STRING", "mode": "NULLABLE" }
]
EOF
}

resource "google_bigquery_table" "fundamental_cache" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "fundamental_cache"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker", "type": "STRING", "mode": "REQUIRED" },
  { "name": "is_healthy", "type": "BOOLEAN", "mode": "REQUIRED" },
  { "name": "health_reason", "type": "STRING", "mode": "NULLABLE" },
  { "name": "is_deep_healthy", "type": "BOOLEAN", "mode": "REQUIRED" },
  { "name": "deep_health_reason", "type": "STRING", "mode": "NULLABLE" }
]
EOF
}

resource "google_bigquery_table" "learning_insights" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "learning_insights"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker", "type": "STRING", "mode": "REQUIRED" },
  { "name": "lesson", "type": "STRING", "mode": "REQUIRED" },
  { "name": "category", "type": "STRING", "mode": "NULLABLE", "description": "e.g., 'Macro Ignore', 'Over-reaction', 'Sector Correlation'" }
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

# Vertex AI User: Required for Gemini analysis
resource "google_project_iam_member" "bot_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

# BQ Storage Read Session User: Required for high-performance Storage API
resource "google_project_iam_member" "bq_read_session_user" {
  project = var.project_id
  role    = "roles/bigquery.readSessionUser"
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
  dataset_id                 = "system_logs"
  location                   = "us-central1"
  description                = "Aggregated master logs for the trading node"
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
resource "google_cloud_scheduler_job" "ticker_rank_trigger" {
  name             = "trading-ticker-ranker"
  description      = "Pre-market ticker ranking (9:15 AM ET)"
  schedule         = "15 9 * * 1-5"
  time_zone        = "America/New_York"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.trading_bot.uri}/rank-tickers"

    oidc_token {
      service_account_email = google_service_account.bot_sa.email
      audience              = google_cloud_run_v2_service.trading_bot.uri
    }
  }
}

resource "google_cloud_scheduler_job" "audit_trigger" {
  name             = "trading-audit-trigger"
  description      = "High-frequency audit (Every 2 minutes during market hours)"
  schedule         = "*/2 9-16 * * 1-5" # Every 2 minutes, 9 AM - 4 PM ET, Mon-Fri
  time_zone        = "America/New_York"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.trading_bot.uri}/run-audit"

    oidc_token {
      service_account_email = google_service_account.bot_sa.email
      audience              = google_cloud_run_v2_service.trading_bot.uri
    }
  }
}

resource "google_cloud_scheduler_job" "hindsight_trigger" {
  name             = "trading-hindsight-reflection"
  description      = "Post-market hindsight reflection (6:00 PM ET)"
  schedule         = "0 18 * * 1-5"
  time_zone        = "America/New_York"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.trading_bot.uri}/run-hindsight"

    oidc_token {
      service_account_email = google_service_account.bot_sa.email
      audience              = google_cloud_run_v2_service.trading_bot.uri
    }
  }
}
resource "google_logging_metric" "paper_equity" {
  name   = "trading/paper_equity"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "node_id"
      value_type = "STRING"
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
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Telemetry: Logged\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
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

resource "google_logging_metric" "total_cash" {
  name   = "trading/total_cash"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }
  value_extractor = "EXTRACT(jsonPayload.total_cash)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "market_value" {
  name   = "trading/market_value"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }
  value_extractor = "EXTRACT(jsonPayload.total_market_value)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "exposure_pct" {
  name   = "trading/exposure_pct"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }
  value_extractor = "EXTRACT(jsonPayload.exposure_pct)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 5.0
      offset             = 0.0
    }
  }
}

resource "google_logging_metric" "prediction_confidence" {
  name   = "trading/prediction_confidence"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Telemetry: Logged\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = {
    "ticker" = "EXTRACT(jsonPayload.ticker)"
  }
  value_extractor = "EXTRACT(jsonPayload.prediction_confidence)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 10
      width              = 10.0
      offset             = 0.0
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
          width = 4, height = 4, xPos = 0, yPos = 0
          widget = {
            title = "Cloud Run: Request Status (2xx vs 4xx/5xx)"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"trading-audit-agent\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.response_code_class"]
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 2: Total Equity (Primary KPI)
        {
          width = 8, height = 4, xPos = 4, yPos = 0
          widget = {
            title = "💰 Paper Equity ($)"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/trading/paper_equity\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 3: Capital Allocation (Cash vs Market Value)
        {
          width = 6, height = 4, xPos = 0, yPos = 4
          widget = {
            title = "⚖️ Capital Allocation"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/total_cash\""
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" }
                    }
                  }
                  targetAxis = "Y1"
                  plotType   = "STACKED_AREA"
                  legendTemplate = "Cash"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/market_value\""
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" }
                    }
                  }
                  targetAxis = "Y1"
                  plotType   = "STACKED_AREA"
                  legendTemplate = "Assets Value"
                }
              ]
            }
          }
        },
        # WIDGET 4: Exposure Meter (%)
        {
          width = 6, height = 4, xPos = 6, yPos = 4
          widget = {
            title = "🚜 Portfolio Exposure (%)"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/trading/exposure_pct\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 5: Conviction Breakdown (Confidence Heatmap)
        {
          width = 6, height = 4, xPos = 0, yPos = 8
          widget = {
            title = "🧠 AI Conviction (Confidence %)"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/trading/prediction_confidence\""
                    aggregation = {
                      alignmentPeriod  = "600s"
                      perSeriesAligner = "ALIGN_MEAN"
                      groupByFields    = ["metric.label.ticker"]
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 6: Market Sentiment Heatmap
        {
          width = 6, height = 4, xPos = 6, yPos = 8
          widget = {
            title = "📰 Market Sentiment (-1 to +1)"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\""
                    aggregation = {
                      alignmentPeriod  = "600s"
                      perSeriesAligner = "ALIGN_MEAN"
                      groupByFields    = ["metric.label.ticker"]
                    }
                  }
                }
              }]
            }
          }
        },
        # WIDGET 7: Latency (ms)
        {
          width = 12, height = 4, xPos = 0, yPos = 12
          widget = {
            title = "⏳ Execution Latency (ms)"
            xyChart = {
              chartOptions = { mode = "COLOR" }
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"trading-audit-agent\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_99"
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

  # Ignore changes to the dashboard JSON to prevent perpetual diffs caused by
  # Google Cloud API normalizing the JSON (e.g. adding defaults, reordering keys).
  lifecycle {
    ignore_changes = [dashboard_json]
  }
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
  display_name          = "CRITICAL: Aberfeldie Node Failure (5xx Errors)"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.email_me.name]

  conditions {
    display_name = "Cloud Run 5xx Errors"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"${google_cloud_run_v2_service.trading_bot.name}\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0 # Any 5xx error triggers it

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

# C. Budget Alert ($10.00)
resource "google_billing_budget" "budget_alert" {
  billing_account = var.billing_account
  display_name    = "Trading Bot Monthly Budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = "10"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.email_me.id
    ]
  }

  depends_on = [google_project_service.billing_budgets]
}
output "dashboard_url" {
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${element(split("/", google_monitoring_dashboard.nasdaq_bot_dashboard.id), 3)}?project=${var.project_id}"
  description = "The direct link to the NASDAQ Monitor Dashboard"
}
