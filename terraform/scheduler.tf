# scheduler.tf - The System Heartbeat
resource "google_cloud_scheduler_job" "trading_pulse" {
  name             = "every-5-minute-audit"
  description      = "Wakes up the agent for market telemetry check"
  schedule         = "*/5 * * * *" # Unix-cron: Every 5 minutes
  time_zone        = "Australia/Melbourne"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.trading_agent.url
    
    # Secure Authentication via OIDC
    oidc_token {
      service_account_email = google_service_account.agent_sa.email
    }
  }
}

