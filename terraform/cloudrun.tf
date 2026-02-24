# cloudrun.tf

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

variable "deploy_time" {
  description = "Timestamp force refresh"
  type        = string
  default     = "0"
}

resource "google_cloud_run_v2_service" "trading_bot" {
  name                = "trading-audit-agent"
  location            = "us-central1"
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  depends_on          = [google_secret_manager_secret_version.initial_versions]

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 3
    }
    service_account = google_service_account.bot_sa.email
    containers {
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }

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

      resources {
        limits = {
          memory = "1024Mi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "MORTGAGE_RATE"
        value = tostring(var.mortgage_rate)
      }
      env {
        name = "EXCHANGE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "FINNHUB_KEY"
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
        name = "FMP_KEY"
        value_source {
          secret_key_ref {
            secret  = "FMP_KEY"
            version = "latest"
          }
        }
      }
      env {
        name = "DISCORD_WEBHOOK"
        value_source {
          secret_key_ref {
            secret  = "DISCORD_WEBHOOK"
            version = "latest"
          }
        }
      }
      env {
        name  = "TRADING_ENABLED"
        value = "True"
      }
      env {
        name  = "BASE_TICKERS"
        value = "TSLA,NVDA,AMD,MU,PLTR,COIN,META,AAPL,MSFT,GOLD,AMZN,AVGO,ASML,LLY,LMT,VRT,CEG,TSM"
      }
      env {
        name  = "INITIAL_CASH"
        value = tostring(var.initial_cash)
      }
      env {
        name  = "MIN_EXPOSURE_THRESHOLD"
        value = tostring(var.min_exposure_threshold)
      }
      env {
        name  = "ALPACA_PAPER_TRADING"
        value = "True"
      }
      env {
        name  = "DEPLOY_TIME"
        value = var.deploy_time
      }
    }
  }
}

# 4. CLOUD RUN INVOKER (For Scheduler)
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.trading_bot.location
  name     = google_cloud_run_v2_service.trading_bot.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.bot_sa.email}"
}

# Vertex AI User
resource "google_project_iam_member" "bot_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}
