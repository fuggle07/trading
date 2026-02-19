# outputs.tf

output "service_url" {
  value       = google_cloud_run_v2_service.trading_bot.uri
  description = "The public URL of the Aberfeldie Trading Node"
}

output "dashboard_url" {
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${element(split("/", google_monitoring_dashboard.nasdaq_bot_dashboard.id), 3)}?project=${var.project_id}"
  description = "The direct link to the NASDAQ Monitor Dashboard"
}
