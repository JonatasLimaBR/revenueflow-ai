variable "project_id" {
  type        = string
  description = "GCP project that hosts the RevenueFlow environment"
}

variable "region" {
  type        = string
  description = "Primary region"
  default     = "southamerica-east1"
}

variable "github_repository" {
  type        = string
  description = "owner/repo allowed to assume the deployer service account via OIDC"
  default     = "JonatasLimaBR/revenueflow-ai"
}

variable "state_bucket_name" {
  type        = string
  description = "Name for the Terraform state bucket; defaults to <project_id>-tfstate"
  default     = ""
}
