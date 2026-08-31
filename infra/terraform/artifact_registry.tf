resource "google_artifact_registry_repository" "api" {
  repository_id = "revenueflow"
  location      = var.region
  format        = "DOCKER"
  description   = "RevenueFlow container images"

  depends_on = [google_project_service.this]
}
