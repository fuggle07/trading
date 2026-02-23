# monitoring.tf

locals {
  # Focus the dashboard on the high-conviction "Core" and the new "Bottleneck" army
  tickers = ["NVDA", "TSLA", "MU", "TSM", "VRT", "CEG", "PLTR", "COIN"]
}

resource "google_monitoring_dashboard" "nasdaq_bot_dashboard" {
  dashboard_json = jsonencode({
    displayName = "Aberfeldie Node: NASDAQ Monitor"
    mosaicLayout = {
      columns = 12
      tiles = concat(
        # ── SYSTEM OVERVIEW ─────────────────────────────────────────────────
        [
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
          # WIDGET 2: Paper Equity
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
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_50"
                        crossSeriesReducer = "REDUCE_MAX"
                        groupByFields      = []
                      }
                    }
                  }
                }]
              }
            }
          },
          # WIDGET 3: Capital Allocation
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
                        aggregation = {
                          alignmentPeriod    = "60s"
                          perSeriesAligner   = "ALIGN_PERCENTILE_50"
                          crossSeriesReducer = "REDUCE_MAX"
                          groupByFields      = []
                        }
                      }
                    }
                    targetAxis    = "Y1"
                    plotType      = "STACKED_AREA"
                    legendTemplate = "Cash"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/market_value\""
                        aggregation = {
                          alignmentPeriod    = "60s"
                          perSeriesAligner   = "ALIGN_PERCENTILE_50"
                          crossSeriesReducer = "REDUCE_MAX"
                          groupByFields      = []
                        }
                      }
                    }
                    targetAxis    = "Y1"
                    plotType      = "STACKED_AREA"
                    legendTemplate = "Assets Value"
                  }
                ]
              }
            }
          },
          # WIDGET 4: Exposure Meter
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
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_50"
                        crossSeriesReducer = "REDUCE_MAX"
                        groupByFields      = []
                      }
                    }
                  }
                }]
              }
            }
          },
          # WIDGET 5: AI Conviction (all tickers)
          {
            width = 6, height = 4, xPos = 0, yPos = 8
            widget = {
              title = "🌟 Stock Quality Levels (Conviction vs Time)"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                thresholds = [
                  { label = "Star (>= 85)", value = 85 },
                  { label = "Neutral (>= 60)", value = 60 },
                  { label = "Sell (< 50)", value = 50 }
                ]
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
          # WIDGET 6: Market Sentiment (all tickers)
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
          # WIDGET 7: Latency
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
          },

          # ── SECTION HEADER: PER-STOCK METRICS ───────────────────────────
          {
            width = 12, height = 1, xPos = 0, yPos = 16
            widget = {
              title = "━━━━━━━━━━  PER-STOCK TECHNICAL METRICS  ━━━━━━━━━━"
              text  = { content = "" }
            }
          }
        ],

        # ── PER-TICKER ROWS (3 charts × 7 tickers) ──────────────────────────
        # Each ticker occupies 5 rows (4 chart height + 1 spacing). Start at yPos 17.
        # Layout per ticker: [Price+Sentiment | BB+SMAs | RSI+Conviction+FScore]

        # NVDA — yPos 17
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 17
            widget = {
              title = "NVDA — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    targetAxis    = "Y1"
                    legendTemplate = "Sentiment"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 17
            widget = {
              title = "NVDA — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 17
            widget = {
              title = "NVDA — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"NVDA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # MU — yPos 22
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 22
            widget = {
              title = "MU — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"MU\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 22
            widget = {
              title = "MU — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 22
            widget = {
              title = "MU — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"MU\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # AMD — yPos 27
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 27
            widget = {
              title = "AMD — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"AMD\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 27
            widget = {
              title = "AMD — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 27
            widget = {
              title = "AMD — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"AMD\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # PLTR — yPos 32
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 32
            widget = {
              title = "PLTR — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"PLTR\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 32
            widget = {
              title = "PLTR — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 32
            widget = {
              title = "PLTR — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"PLTR\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # COIN — yPos 37
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 37
            widget = {
              title = "COIN — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"COIN\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 37
            widget = {
              title = "COIN — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 37
            widget = {
              title = "COIN — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"COIN\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # TSLA — yPos 42
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 42
            widget = {
              title = "TSLA — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"TSLA\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 42
            widget = {
              title = "TSLA — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 42
            widget = {
              title = "TSLA — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"TSLA\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # TSM — yPos 47
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 47
            widget = {
              title = "TSM — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"TSM\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 47
            widget = {
              title = "TSM — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 47
            widget = {
              title = "TSM — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"TSM\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # VRT — yPos 52
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 52
            widget = {
              title = "VRT — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"VRT\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 52
            widget = {
              title = "VRT — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 52
            widget = {
              title = "VRT — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"VRT\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ],

        # CEG — yPos 57
        [
          {
            width = 4, height = 4, xPos = 0, yPos = 57
            widget = {
              title = "CEG — Price & Sentiment"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [{
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/trading/sentiment_score\" AND metric.labels.ticker=\"CEG\""
                      aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                    }
                  }
                  legendTemplate = "Sentiment"
                }]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 4, yPos = 57
            widget = {
              title = "CEG — Bollinger Bands & SMAs"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_upper\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Upper"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_20\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-20"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/sma_50\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "SMA-50"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/bb_lower\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "BB Lower"
                  }
                ]
              }
            }
          },
          {
            width = 4, height = 4, xPos = 8, yPos = 57
            widget = {
              title = "CEG — RSI / Conviction / F-Score"
              xyChart = {
                chartOptions = { mode = "COLOR" }
                dataSets = [
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/rsi\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "RSI"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/conviction\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "Conviction"
                  },
                  {
                    timeSeriesQuery = {
                      timeSeriesFilter = {
                        filter = "metric.type=\"logging.googleapis.com/user/trading/f_score\" AND metric.labels.ticker=\"CEG\""
                        aggregation = { alignmentPeriod = "600s", perSeriesAligner = "ALIGN_PERCENTILE_50" }
                      }
                    }
                    legendTemplate = "F-Score"
                  }
                ]
              }
            }
          }
        ]
      )
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
