# terraform/scheduler.tf - Version 1.0 (Nasdaq Heartbeat)

resource "google_cloud_scheduler_job" "nasdaq_audit_trigger" {
  name             = "nasdaq-audit-heartbeat"
  description      = "Triggers the Aberfeldie Node every 15 mins during Nasdaq Regular Session."
  
  # Cron: Every 15 mins, between 09:00 and 16:00, Monday through Friday.
  # This covers the 9:30 AM open and the 4:00 PM close with a buffer.
  schedule         = "*/15 9-16 * * 1-5"
  time_zone        = "America/New_York"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = google_cloud_run_v2_service.trading_bot.uri # References your Step 4 deployment
    
    # We must pass an OIDC token for the hardened IAM logic to allow the call
    oidc_token {
      service_account_email = "trading-bot-executor@${var.project_id}.iam.gserviceaccount.com"
      audience              = google_cloud_run_v2_service.trading_bot.uri
    }

    # Signal to main.py that this is an automated audit
    body = base64encode("{\"action\": \"audit\", \"source\": \"scheduler\"}")
  }
}

