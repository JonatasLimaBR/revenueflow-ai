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
  description = "Vertex AI Gemini model id (2.0 line is retired on Vertex; use 2.5)"
  default     = "gemini-2.5-flash"
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

variable "alert_email" {
  type        = string
  description = "Address for the Cloud Monitoring email notification channel; empty disables notifications (ADR-056)"
  default     = ""
}

variable "alert_5xx_ratio" {
  type        = number
  description = "5xx-to-total request ratio that fires the availability alert"
  default     = 0.02
}

variable "alert_p95_latency_ms" {
  type        = number
  description = "Request p95 latency in ms that fires the latency alert"
  default     = 3000
}

variable "alert_tool_failures_per_hour" {
  type        = number
  description = "Tool-exception count per hour that fires the tool-failure alert"
  default     = 10
}

variable "alert_ai_cost_per_hour_usd" {
  type        = number
  description = "AI cost per hour in USD that fires the cost alert"
  default     = 1.0
}

variable "alert_no_turns_minutes" {
  type        = number
  description = "Minutes without an audited turn that fires the consumer-liveness alert"
  default     = 15
}
