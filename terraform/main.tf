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
  {"name": "recommendation", "type": "STRING", "mode": "NULLABLE"}
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
# 1. ALLOW BOT TO RUN BIGQUERY JOBS (Project Level)
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

# 2. ALLOW BOT TO EDIT DATA IN THE DATASET (Dataset Level)
resource "google_bigquery_dataset_iam_member" "bq_data_editor" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.bot_sa.email}"
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

