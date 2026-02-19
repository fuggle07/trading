locals {
  secret_names = toset(["FINNHUB_KEY", "IBKR_KEY", "APIFY_TOKEN", "ALPACA_API_KEY", "ALPACA_API_SECRET", "ALPHA_VANTAGE_KEY", "FMP_KEY"])
}

# secret_manager.tf

# 1. SECRET MANAGEMENT TIER
resource "google_secret_manager_secret" "secrets" {
  for_each  = local.secret_names
  secret_id = each.key

  replication {
    auto {}
  }
}

# 3. SECRET ACCESS
resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each   = local.secret_names
  secret_id  = each.key
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.bot_sa.email}"
  depends_on = [google_secret_manager_secret.secrets]
}

# CREATE INITIAL SECRET VERSIONS
resource "google_secret_manager_secret_version" "initial_versions" {
  for_each    = local.secret_names
  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = "PLACEHOLDER_INIT" # To be overwritten by 03_sync_secrets.sh

  depends_on = [google_secret_manager_secret_iam_member.secret_access]

  lifecycle {
    ignore_changes = [secret_data]
  }
}
