# provider.tf
provider "google" {
  project               = var.project_id
  region                = "us-central1"
  user_project_override = true
  billing_project       = var.project_id
}
