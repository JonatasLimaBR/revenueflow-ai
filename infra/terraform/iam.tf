resource "google_service_account" "api" {
  account_id   = "${var.service_name}-sa"
  display_name = "RevenueFlow API runtime identity"
}

# Project-wide roles the runtime SA genuinely needs project scope for.
# Pub/Sub is scoped to the topic/subscription in pubsub.tf; secret access is
# scoped per-secret in secrets.tf (ADR-008: least privilege).
resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Vertex AI / Gemini for the real LLM path (ADR-049). `user`, never `admin`
# (ADR-008: least privilege).
resource "google_project_iam_member" "api_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Cloud Trace span export for TRACER_SINK=otel (ADR-056). `agent`, the minimal
# role that lets a workload write spans (ADR-008: least privilege).
resource "google_project_iam_member" "api_cloudtrace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.api.email}"
}
