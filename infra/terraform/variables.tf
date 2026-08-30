variable "project_id" {
  type        = string
  description = "GCP project that hosts the RevenueFlow environment"
}

variable "region" {
  type        = string
  description = "Primary region for Cloud Run and Cloud SQL"
  default     = "southamerica-east1"
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name"
  default     = "revenueflow-api"
}

variable "db_tier" {
  type        = string
  description = "Cloud SQL machine tier"
  default     = "db-custom-1-3840"
}

variable "min_instances" {
  type        = number
  description = "Cloud Run minimum instances"
  default     = 0
}

variable "max_instances" {
  type        = number
  description = "Cloud Run maximum instances"
  default     = 4
}
