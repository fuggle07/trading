variable "deploy_time" {
  type        = string
  description = "Dynamic timestamp to force Cloud Run redeployment"
  default     = "initial"
}
