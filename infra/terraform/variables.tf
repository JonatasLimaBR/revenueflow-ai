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

variable "image" {
  type        = string
  description = "Full Artifact Registry image reference including tag or digest"
}

variable "db_tier" {
  type        = string
  description = "Cloud SQL machine tier"
  default     = "db-custom-1-3840"
}

variable "min_instances" {
  type        = number
  description = "Cloud Run minimum instances. ADR-047: pull-mode consumption needs >= 1."
  default     = 1
}

variable "max_instances" {
  type        = number
  description = "Cloud Run maximum instances"
  default     = 4
}

variable "tracer_sink" {
  type        = string
  description = "Observability sink: noop | otel | langfuse"
  default     = "noop"

  validation {
    condition     = contains(["noop", "otel", "langfuse"], var.tracer_sink)
    error_message = "tracer_sink must be one of noop, otel, langfuse."
  }
}

variable "gemini_model" {
  type        = string
  description = "Vertex AI Gemini model id"
  default     = "gemini-2.0-flash"
}

variable "vertex_location" {
  type        = string
  description = "Vertex AI location for Gemini; 'global' avoids regional availability gaps (ADR-049)"
  default     = "global"
}

variable "langfuse_host" {
  type        = string
  description = "Langfuse base URL; empty until Langfuse is hosted (ADR-045)"
  default     = ""
}

variable "billing_account" {
  type        = string
  description = "Billing account id for the budget alert; empty disables the budget"
  default     = ""
}

variable "budget_amount_usd" {
  type        = number
  description = "Monthly budget threshold in USD for the budget alert"
  default     = 200
}
