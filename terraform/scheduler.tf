# scheduler.tf

# 5. SCHEDULER ACCESS
data "google_project" "project" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "scheduler_sa_user" {
  service_account_id = google_service_account.bot_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
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
  schedule         = "*/2 9-16 * * 1-5"
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

resource "google_cloud_scheduler_job" "intraday_feedback_trigger" {
  name             = "trading-intraday-feedback"
  description      = "Hourly intraday AI feedback (Every hour during market hours)"
  schedule         = "0 10-15 * * 1-5" # Hourly from 10 AM to 3 PM
  time_zone        = "America/New_York"
  attempt_deadline = "310s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.trading_bot.uri}/run-hindsight"

    oidc_token {
      service_account_email = google_service_account.bot_sa.email
      audience              = google_cloud_run_v2_service.trading_bot.uri
    }
  }
}
