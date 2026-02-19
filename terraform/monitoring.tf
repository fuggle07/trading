# monitoring.tf

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
                      perSeriesAligner = "ALIGN_PERCENTILE_50"
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
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
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
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
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
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
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
                      perSeriesAligner = "ALIGN_PERCENTILE_50"
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
                      perSeriesAligner = "ALIGN_PERCENTILE_50"
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

  amount {
    specified_amount {
      currency_code = "AUD"
      units         = "15"
    }
  }

  depends_on = [google_project_service.billing_budgets]
}
