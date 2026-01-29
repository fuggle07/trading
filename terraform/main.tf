# main.tf - Unified Aberfeldie Node Blueprint (v3.4)
provider "google" {
  project = var.project_id
  region  = "us-central1"
}

variable "project_id" {
  type        = string
  description = "The GCP Project ID"
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
  delete_contents_on_destroy = false
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
    service_account = google_service_account.bot_sa.email
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/trading-node-repo/trading-bot:latest"
      
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name = "FINNHUB_KEY"
        value_source {
          secret_key_ref {
            secret  = "FINNHUB_KEY"
            version = "latest"
          }
        }
      }
    }
  }
}

# BigQuery Data Editor: Permission to insert rows
resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:trading-bot-executor@${var.project_id}.iam.gserviceaccount.com"
}

# BigQuery Job User: Permission to run insertion jobs
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:trading-bot-executor@${var.project_id}.iam.gserviceaccount.com"
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
  {"name": "asset_name", "type": "STRING", "mode": "REQUIRED"},
  {"name": "holdings", "type": "FLOAT64", "mode": "REQUIRED"},
  {"name": "cash_balance", "type": "FLOAT64", "mode": "REQUIRED"},
  {"name": "last_updated", "type": "TIMESTAMP", "mode": "REQUIRED"}
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

resource "google_bigquery_dataset_iam_member" "bot_bq_editor" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.bot_sa.email}"
}

# Create a dedicated high-retention bucket for the system audit
resource "google_logging_project_bucket_config" "audit_log_bucket" {
    project    = var.project_id
    location   = "global"
    retention_days = 365 # Keep one year for tax/audit purposes
    bucket_id  = "system-audit-trail"
}
# Create the Dataset for Log Analytics
resource "google_bigquery_dataset" "system_logs" {
  dataset_id                  = "system_logs"
  location                    = "australia-southeast1"
  description                 = "Aggregated master logs for the trading node"
  delete_contents_on_destroy = false
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

