# Public read-only MCP server over Streamable HTTP (ADR-067). Same container
# image as the API (var.image), different command — reuses the runtime
# service account (already has DATABASE_URL + MCP_API_TOKEN secret access via
# google_secret_manager_secret_iam_member.api_manual). Public ingress
# (allUsers invoker) with the shared bearer token as the only gate — same
# trust model as /internal/approvals and /internal/handoffs. Only the 6 read
# tools are registered on this server (src/revenueflow/mcp/http_server.py);
# the 5 action tools stay on the personal stdio server (ADR-064).
resource "google_cloud_run_v2_service" "mcp_readonly" {
  name     = "${var.service_name}-mcp-readonly"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  # Stateless, low-traffic viewer tool — scale to zero when unused.
  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 0
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
      command = ["python", "scripts/mcp_http_server.py"]

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
        name = "MCP_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.manual["MCP_API_TOKEN"].secret_id
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

resource "google_cloud_run_v2_service_iam_member" "mcp_readonly_public_invoker" {
  name     = google_cloud_run_v2_service.mcp_readonly.name
  location = google_cloud_run_v2_service.mcp_readonly.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
