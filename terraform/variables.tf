# variables.tf
variable "project_id" {
  type        = string
  description = "The GCP Project ID"
}

variable "mortgage_rate" {
  description = "The annual mortgage interest rate (e.g., 0.54 for 5.4%)"
  type        = number
  default     = 0.054 # NAB actual
}

variable "billing_account" {
  description = "The billing account ID"
  type        = string
  default     = "017BBC-3B0075-8F989F"
}
