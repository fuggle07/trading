
# D. Trade Execution Metric (Log-Based)
resource "google_logging_metric" "trade_executed" {
  name        = "trading/trade_executed"
  filter      = "resource.type=\"cloud_run_revision\" AND textPayload=~\"✅ Alpaca Order Submitted\""
  description = "Count of trades submitted to Alpaca"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# E. Trade Execution Alert
resource "google_monitoring_alert_policy" "trade_alert" {
  display_name          = "💰 Trade Executed (Aberfeldie Node)"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.email_me.name]

  conditions {
    display_name = "Trade Logged"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.trade_executed.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  documentation {
    content = "The bot just submitted a trade! Check the dashboard for details."
  }
}
