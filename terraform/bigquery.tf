# bigquery.tf

# 2. ANALYTICS TIER (BigQuery)
resource "google_bigquery_dataset" "trading_data" {
  dataset_id                 = "trading_data"
  friendly_name              = "Aberfeldie Trading Analytics"
  location                   = "us-central1"
  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "performance_logs" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "performance_logs"
  deletion_protection = false 

  schema = <<EOF
[
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "paper_equity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "tax_buffer_usd", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "fx_rate_aud", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "daily_hurdle_aud", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "net_alpha_usd", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "node_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "recommendation", "type": "STRING", "mode": "NULLABLE"},
  { "name": "sentiment_score", "type": "FLOAT", "mode": "NULLABLE" },
  { "name": "social_volume", "type": "INTEGER", "mode": "NULLABLE" }
]
EOF
}

resource "google_bigquery_table" "watchlist_logs" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "watchlist_logs"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp",       "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker",          "type": "STRING",    "mode": "REQUIRED" },
  { "name": "price",           "type": "FLOAT",     "mode": "REQUIRED" },
  { "name": "sentiment_score", "type": "FLOAT",     "mode": "NULLABLE" },
  { "name": "rsi",             "type": "FLOAT",     "mode": "NULLABLE", "description": "14-day RSI" },
  { "name": "sma_20",          "type": "FLOAT",     "mode": "NULLABLE" },
  { "name": "sma_50",          "type": "FLOAT",     "mode": "NULLABLE" },
  { "name": "bb_upper",        "type": "FLOAT",     "mode": "NULLABLE", "description": "Bollinger Band Upper" },
  { "name": "bb_lower",        "type": "FLOAT",     "mode": "NULLABLE", "description": "Bollinger Band Lower" },
  { "name": "f_score",         "type": "INTEGER",   "mode": "NULLABLE", "description": "Piotroski F-Score (0-9)" },
  { "name": "conviction",      "type": "INTEGER",   "mode": "NULLABLE", "description": "Signal conviction (0-100)" },
  { "name": "gemini_reasoning","type": "STRING",    "mode": "NULLABLE", "description": "Gemini sentiment reasoning" }
]
EOF
}

resource "google_bigquery_table" "portfolio" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "portfolio"
  deletion_protection = false

  schema = <<EOF
[
  {
    "name": "asset_name",
    "type": "STRING",
    "mode": "REQUIRED"
  },
  {
    "name": "holdings",
    "type": "FLOAT",
    "mode": "REQUIRED"
  },
  {
    "name": "avg_price",
    "type": "FLOAT",
    "mode": "NULLABLE",
    "description": "Weighted Average Cost Basis for Stop Loss calculation"
  },
  {
    "name": "cash_balance",
    "type": "FLOAT",
    "mode": "REQUIRED"
  },
  {
    "name": "last_updated",
    "type": "TIMESTAMP",
    "mode": "REQUIRED"
  }
]
EOF
}

resource "google_bigquery_table" "executions" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "executions"
  deletion_protection = false

  schema = <<EOF
[
  {"name": "execution_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "alpaca_order_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "ticker", "type": "STRING", "mode": "REQUIRED"},
  {"name": "action", "type": "STRING", "mode": "REQUIRED"},
  {"name": "quantity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "price", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "commission", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "reason", "type": "STRING", "mode": "NULLABLE"},
  {"name": "status", "type": "STRING", "mode": "REQUIRED"}
]
EOF
}

resource "google_bigquery_table" "ticker_rankings" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "ticker_rankings"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp",        "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker",           "type": "STRING",    "mode": "REQUIRED" },
  { "name": "sentiment",        "type": "FLOAT",     "mode": "REQUIRED" },
  { "name": "confidence",       "type": "INTEGER",   "mode": "REQUIRED" },
  { "name": "reason",           "type": "STRING",    "mode": "NULLABLE" },
  { "name": "gemini_reasoning", "type": "STRING",    "mode": "NULLABLE", "description": "Full Gemini reasoning text" }
]
EOF
}

resource "google_bigquery_table" "fundamental_cache" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "fundamental_cache"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp",         "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker",            "type": "STRING",    "mode": "REQUIRED" },
  { "name": "is_healthy",        "type": "BOOLEAN",   "mode": "REQUIRED" },
  { "name": "health_reason",     "type": "STRING",    "mode": "NULLABLE" },
  { "name": "is_deep_healthy",   "type": "BOOLEAN",   "mode": "REQUIRED" },
  { "name": "deep_health_reason","type": "STRING",    "mode": "NULLABLE" },
  { "name": "metrics_json",      "type": "STRING",    "mode": "NULLABLE", "description": "Raw FMP metrics snapshot (PE, F-Score, DCF, ROE etc.)" }
]
EOF
}

resource "google_bigquery_table" "macro_snapshots" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "macro_snapshots"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp",   "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "vix",         "type": "FLOAT",     "mode": "NULLABLE", "description": "VIX fear index" },
  { "name": "spy_perf",    "type": "FLOAT",     "mode": "NULLABLE", "description": "SPY % change" },
  { "name": "qqq_perf",    "type": "FLOAT",     "mode": "NULLABLE", "description": "QQQ % change" },
  { "name": "yield_10y",   "type": "FLOAT",     "mode": "NULLABLE", "description": "US 10Y Treasury Yield" },
  { "name": "yield_2y",    "type": "FLOAT",     "mode": "NULLABLE", "description": "US 2Y Treasury Yield" },
  { "name": "yield_source","type": "STRING",    "mode": "NULLABLE", "description": "Data source: FMP/Finnhub/AlphaVantage" },
  { "name": "calendar_json","type": "STRING",   "mode": "NULLABLE", "description": "High-impact economic events JSON" }
]
EOF
}

resource "google_bigquery_table" "learning_insights" {
  dataset_id          = google_bigquery_dataset.trading_data.dataset_id
  table_id            = "learning_insights"
  deletion_protection = false

  schema = <<EOF
[
  { "name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "ticker", "type": "STRING", "mode": "REQUIRED" },
  { "name": "lesson", "type": "STRING", "mode": "REQUIRED" },
  { "name": "category", "type": "STRING", "mode": "NULLABLE", "description": "e.g., 'Macro Ignore', 'Over-reaction', 'Sector Correlation'" }
]
EOF
}

# Harden IAM for the Bot
resource "google_project_iam_member" "bot_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

resource "google_project_iam_member" "bq_read_session_user" {
  project = var.project_id
  role    = "roles/bigquery.readSessionUser"
  member  = "serviceAccount:${google_service_account.bot_sa.email}"
}

resource "google_bigquery_dataset_iam_member" "bot_bq_editor" {
  dataset_id = google_bigquery_dataset.trading_data.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.bot_sa.email}"
}

# System Logs (Log Analytics)
resource "google_bigquery_dataset" "system_logs" {
  dataset_id                 = "system_logs"
  location                   = "us-central1"
  description                = "Aggregated master logs for the trading node"
  delete_contents_on_destroy = false
}



resource "google_logging_project_sink" "master_log_sink" {
  name        = "trading-system-master-sink"
  description = "Routes structured audit logs from all Cloud Run services to BigQuery"
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.system_logs.dataset_id}"
  filter      = "resource.type=\"cloud_run_revision\" AND jsonPayload.component:\"*\""
  unique_writer_identity = true
}

resource "google_project_iam_member" "log_sink_writer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = google_logging_project_sink.master_log_sink.writer_identity
}
