# main.tf
provider "google" {
  project = var.project_id
  region  = "us-central1"
}

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
  replication { auto {} }
}
# monitoring.tf - Automated Alerting
resource "google_monitoring_uptime_check_config" "bot_uptime" {
  display_name = "Bot-Uptime-Check"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path = "/" # Point this to your Cloud Function trigger URL
    port = 443
    use_ssl = true
  }
}

resource "google_monitoring_alert_policy" "logic_failure_alert" {
  display_name = "Logic Failure Alert"
  combiner     = "OR"
  conditions {
    display_name = "Error log detected"
    condition_matched_log {
      filter = "resource.type=\"cloud_function\" textPayload:\"ERROR\""
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.name]
}

# terraform/main.tf - Analytics Extension

resource "google_bigquery_dataset" "trading_data" {
  dataset_id                  = "trading_data"
  friendly_name               = "Trading Analytics"
  description                 = "Performance logs for the Aberfeldie Node"
  location                    = "us-central1"
  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "performance_logs" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  table_id   = "performance_logs"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "paper_equity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "index_price", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "node_id", "type": "STRING", "mode": "NULLABLE"}
]
EOF
}

