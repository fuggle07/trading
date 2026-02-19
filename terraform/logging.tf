# logging.tf

resource "google_logging_metric" "paper_equity" {
  name   = "trading/paper_equity"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "node_id"
      value_type = "STRING"
    }
  }
  label_extractors = {
    "node_id" = "EXTRACT(jsonPayload.node_id)"
  }
  value_extractor = "EXTRACT(jsonPayload.paper_equity)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "sentiment_score" {
  name   = "trading/sentiment_score"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Telemetry: Logged\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = {
    "ticker" = "EXTRACT(jsonPayload.ticker)"
  }
  value_extractor = "EXTRACT(jsonPayload.sentiment_score)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 0.1
      offset             = -1.0
    }
  }
}

resource "google_logging_metric" "total_cash" {
  name   = "trading/total_cash"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }
  value_extractor = "EXTRACT(jsonPayload.total_cash)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "market_value" {
  name   = "trading/market_value"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }
  value_extractor = "EXTRACT(jsonPayload.total_market_value)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "exposure_pct" {
  name   = "trading/exposure_pct"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Logged Performance\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }
  value_extractor = "EXTRACT(jsonPayload.exposure_pct)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 0.1
      offset             = 0.0
    }
  }
}

resource "google_logging_metric" "prediction_confidence" {
  name   = "trading/prediction_confidence"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.message=~\"Telemetry: Logged\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = {
    "ticker" = "EXTRACT(jsonPayload.ticker)"
  }
  value_extractor = "EXTRACT(jsonPayload.prediction_confidence)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 10
      width              = 10.0
      offset             = 0.0
    }
  }
}

resource "google_logging_metric" "rsi" {
  name   = "trading/rsi"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.rsi!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = {
    "ticker" = "EXTRACT(jsonPayload.ticker)"
  }
  value_extractor = "EXTRACT(jsonPayload.rsi)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 20
      width              = 5.0
      offset             = 0.0
    }
  }
}

resource "google_logging_metric" "sma_20" {
  name   = "trading/sma_20"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.sma_20!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = { "ticker" = "EXTRACT(jsonPayload.ticker)" }
  value_extractor  = "EXTRACT(jsonPayload.sma_20)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "sma_50" {
  name   = "trading/sma_50"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.sma_50!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = { "ticker" = "EXTRACT(jsonPayload.ticker)" }
  value_extractor  = "EXTRACT(jsonPayload.sma_50)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "bb_upper" {
  name   = "trading/bb_upper"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.bb_upper!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = { "ticker" = "EXTRACT(jsonPayload.ticker)" }
  value_extractor  = "EXTRACT(jsonPayload.bb_upper)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "bb_lower" {
  name   = "trading/bb_lower"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.bb_lower!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = { "ticker" = "EXTRACT(jsonPayload.ticker)" }
  value_extractor  = "EXTRACT(jsonPayload.bb_lower)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2
      scale              = 0.01
    }
  }
}

resource "google_logging_metric" "f_score" {
  name   = "trading/f_score"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.f_score!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = { "ticker" = "EXTRACT(jsonPayload.ticker)" }
  value_extractor  = "EXTRACT(jsonPayload.f_score)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 9
      width              = 1.0
      offset             = 0.0
    }
  }
}

resource "google_logging_metric" "conviction" {
  name   = "trading/conviction"
  filter = "resource.type=\"cloud_run_revision\" AND jsonPayload.event=\"WATCHLIST_LOG\" AND jsonPayload.conviction!=\"\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
    labels {
      key        = "ticker"
      value_type = "STRING"
    }
  }
  label_extractors = { "ticker" = "EXTRACT(jsonPayload.ticker)" }
  value_extractor  = "EXTRACT(jsonPayload.conviction)"
  bucket_options {
    linear_buckets {
      num_finite_buckets = 10
      width              = 10.0
      offset             = 0.0
    }
  }
}

