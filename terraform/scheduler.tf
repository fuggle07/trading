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
resource "google_cloud_scheduler_job" "ticker_rank_premarket" {
  name             = "trading-ticker-ranker-premarket"
  description      = "Pre-market sentiment scan (9:00 AM ET)"
  schedule         = "0 9 * * 1-5"
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

resource "google_cloud_scheduler_job" "ticker_rank_midday" {
  name             = "trading-ticker-ranker-midday"
  description      = "Midday ticker re-rank (12:00 PM ET) — absorbs morning price action"
  schedule         = "0 12 * * 1-5"
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

resource "google_cloud_scheduler_job" "ticker_rank_power_hour" {
  name             = "trading-ticker-ranker-power-hour"
  description      = "Pre-power-hour ticker re-rank (2:00 PM ET) — 90-min runway before close"
  schedule         = "0 14 * * 1-5"
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
  description      = "High-frequency audit (Every 1 minute during market hours)"
  schedule         = "* 9-16 * * 1-5"
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
