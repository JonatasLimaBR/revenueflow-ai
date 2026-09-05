# Operational portal (ADR-073): read+action web UI for the team. Same
# container image as the API (var.image), different command. Auth is
# entirely app-level (Google Sign-In + email allowlist + signed session
# cookie) — same public-ingress trust model as the MCP public server
# (ADR-067) and the landing page (ADR-060). Unlike every other service in
# this project, min_instance_count=1 (not 0): the live agent-activity panel
# holds a Postgres LISTEN connection that would miss events while the
# service is scaled to zero.
resource "google_cloud_run_v2_service" "portal" {
  name     = "${var.service_name}-portal"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.oltp.connection_name]
      }
    }

    containers {
      image   = var.image
      command = ["python", "scripts/portal_server.py"]

      ports {
        container_port = 8000
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REVENUEFLOW_API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }

      env {
        name  = "PORTAL_VIEWER_EMAILS"
        value = join(",", var.dashboard_viewer_emails)
      }

      env {
        name = "PORTAL_GOOGLE_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.manual["PORTAL_GOOGLE_CLIENT_ID"].secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "PORTAL_SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.manual["PORTAL_SESSION_SECRET"].secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "APPROVAL_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.manual["APPROVAL_API_TOKEN"].secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "HANDOFF_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.manual["HANDOFF_API_TOKEN"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.this,
    google_secret_manager_secret_iam_member.api_manual,
    google_secret_manager_secret_iam_member.api_db_url,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "portal_public_invoker" {
  name     = google_cloud_run_v2_service.portal.name
  location = google_cloud_run_v2_service.portal.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
