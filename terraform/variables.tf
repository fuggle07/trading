variable "deploy_time" {
  type        = string
  description = "Dynamic timestamp to force Cloud Run redeployment"
  default     = "initial"
}
variable "billing_account" {
  type        = string
  description = "The ID of the billing account to associate the budget with (e.g., 012345-678901-ABCDEF)"
  default     = "017BBC-3B0075-8F989F"
}
