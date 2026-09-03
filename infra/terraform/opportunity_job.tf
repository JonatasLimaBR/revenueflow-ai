# On-demand opportunity detection as a Cloud Run Job on the same image, so the
# Opportunity Engine (ADR-019) runs outside the request path and outside the
# LangGraph turn. Run it with:
#   gcloud run jobs execute revenueflow-opportunity-scan --region <region> --wait
# A daily Cloud Scheduler trigger is a documented follow-up, not part of this slice.
resource "google_cloud_run_v2_job" "opportunity_scan" {
  name                = "${var.service_name}-opportunity-scan"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.api.email
      max_retries     = 1
      timeout         = "600s"

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.oltp.connection_name]
        }
      }

      containers {
        image   = var.image
        command = ["python", "scripts/detect_opportunities.py"]

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
      }
    }
  }

  depends_on = [
    google_project_service.this,
    google_secret_manager_secret_iam_member.api_db_url,
    google_sql_database.app,
    google_sql_user.app,
  ]
}
